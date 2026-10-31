"""Regression tests for calendar gaps before the daily article is available."""

import contextlib
import importlib.util
import io
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'verify_data', Path(__file__).with_name('verify_data.py'))
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 31)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 31, 9, tzinfo=timezone(timedelta(hours=8)))


class CoverageTests(unittest.TestCase):
    def run_check(self, data_dates, jsonl_dates=None, args=(), exceptions=''):
        if jsonl_dates is None:
            jsonl_dates = data_dates
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            data_file = root / 'data.json'
            jsonl_file = root / 'all_prices.jsonl'
            exceptions_file = root / 'exceptions.md'
            data_file.write_text(json.dumps({'prices': [
                {'date': d, 'source': '今日酒价'} for d in data_dates
            ]}), encoding='utf-8')
            jsonl_file.write_text(''.join(
                json.dumps({'date': d}) + '\n' for d in jsonl_dates),
                encoding='utf-8')
            exceptions_file.write_text(exceptions, encoding='utf-8')
            out = io.StringIO()
            with patch.multiple(verify, DATA_JSON=str(data_file),
                                ALL_PRICES=str(jsonl_file),
                                EXCEPTIONS_FILE=str(exceptions_file),
                                DEFAULT_START=date(2026, 10, 29),
                                date=FrozenDate), \
                    patch.object(verify, 'datetime', FrozenDatetime, create=True), \
                    patch.object(verify.sys, 'argv', ['verify_data.py', *args]), \
                    contextlib.redirect_stdout(out):
                with self.assertRaises(SystemExit) as result:
                    verify.main()
            return result.exception.code, out.getvalue()

    def test_uncollected_today_is_pending_not_a_historical_gap(self):
        code, out = self.run_check(['2026-10-29', '2026-10-30'], args=['--quiet'])
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith('OK '), out)
        self.assertIn('missing=0', out)
        self.assertIn('pending_today=1', out)

    def test_a_missing_yesterday_still_fails(self):
        code, out = self.run_check(['2026-10-29'])
        self.assertEqual(code, 1, out)
        self.assertIn('MISSING 2026-10-30', out)
        self.assertNotIn('MISSING 2026-10-31', out)

    def test_explicit_date_requires_today_after_publication(self):
        code, out = self.run_check(['2026-10-29', '2026-10-30'],
                                   args=['--date', '2026-10-31'])
        self.assertEqual(code, 1, out)
        self.assertIn('MISSING 2026-10-31', out)

    def test_collected_today_is_not_pending(self):
        code, out = self.run_check(
            ['2026-10-29', '2026-10-30', '2026-10-31'], args=['--quiet'])
        self.assertEqual(code, 0, out)
        self.assertIn('pending_today=0', out)

    def test_today_core_data_without_jsonl_still_fails(self):
        code, out = self.run_check(
            ['2026-10-29', '2026-10-30', '2026-10-31'],
            jsonl_dates=['2026-10-29', '2026-10-30'])
        self.assertEqual(code, 1, out)
        self.assertIn('JSONL_GAP 2026-10-31', out)

    def test_known_nonpublishing_day_remains_excused(self):
        code, out = self.run_check(['2026-10-29'], args=['--quiet'],
                                   exceptions='2026-10-30 ｜ 停更\n')
        self.assertEqual(code, 0, out)
        self.assertIn('excused=1', out)
        self.assertIn('pending_today=1', out)


if __name__ == '__main__':
    unittest.main()
