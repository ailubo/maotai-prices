# 2025 wrong WeChat links

Updated: 2026-06-18

These records in `2025-links.json` did not produce Markdown because the current URL opens a 2026 article, not the requested 2025 date. The fastpath extractor correctly rejected them through `publishDate` validation or, for several May/June records, through the row-count gate before saving; their page text still clearly shows a 2026 table date.

## Needs Replacement Links

| Requested date | Current URL | Observed article date | Result |
| --- | --- | --- | --- |
| 2025-06-07 | https://mp.weixin.qq.com/s/S-dkNXwel6JVcjoD8VaCBw | 2026-06-07 | Rejected; page sample shows `2026年6月7日` and rows were below the 2025 quality gate. |
| 2025-06-06 | https://mp.weixin.qq.com/s/HCyvGjgwj_uE0GGMcxs7Qw | 2026-06-06 | Rejected; page sample shows `2026年6月6日` and rows were below the 2025 quality gate. |
| 2025-06-01 | https://mp.weixin.qq.com/s/ZhmqTsySxxFtnzOQqQJgJw | 2026-06-01 | Rejected; page sample shows `2026年6月1日` and rows were below the 2025 quality gate. |
| 2025-05-27 | https://mp.weixin.qq.com/s/phCLugwDd64iS8gghWjvKQ | 2026-05-27 | Rejected; page sample shows `2026年5月27日` and rows were below the 2025 quality gate. |
| 2025-05-17 | https://mp.weixin.qq.com/s/PKsKZNAfAmfb6ESxb-4rWQ | 2026-05-17 | Rejected; page sample shows `2026年5月17日` and rows were below the 2025 quality gate. |
| 2025-05-13 | https://mp.weixin.qq.com/s/FdIN_uxq9OLe3o7lcfsE8g | 2026-05-13 | Rejected; page sample shows `2026年5月13日` and rows were below the 2025 quality gate. |
| 2025-05-12 | https://mp.weixin.qq.com/s/-klvdnrwPuyzOO81_8rygg | 2026-05-12 | Rejected; page sample shows `2026年5月12日` and rows were below the 2025 quality gate. |
| 2025-03-28 | https://mp.weixin.qq.com/s/0Ly8Npe5YYGJoytXccPIzw | 2026-03-28 | Rejected: `publish date mismatch`. |
| 2025-03-19 | https://mp.weixin.qq.com/s/ZAAon-llFMlFbgYmXovOKQ | 2026-03-19 | Rejected: `publish date mismatch`. |
| 2025-03-17 | https://mp.weixin.qq.com/s/PYyEpomFpJMoFiF2YGg6CQ | 2026-03-17 | Rejected: `publish date mismatch`. |
| 2025-03-13 | https://mp.weixin.qq.com/s/DpuUl6BBjcycuB5mGVqRoQ | 2026-03-13 | Rejected: `publish date mismatch`. |
| 2025-03-09 | https://mp.weixin.qq.com/s/siQJuHOO2YtGzzD9GJvJkA | 2026-03-09 | Rejected: `publish date mismatch`. |
| 2025-03-04 | https://mp.weixin.qq.com/s/W8_vQfkpYJpLBX9mk3Lj-A | 2026-03-04 | Rejected: `publish date mismatch`. |
| 2025-03-03 | https://mp.weixin.qq.com/s/d-UImAYKmabOFtxnDWN5Kw | 2026-03-03 | Rejected: `publish date mismatch`. |
| 2025-03-02 | https://mp.weixin.qq.com/s/7tXB_qRN3YQuGMIGpM0QQA | 2026-03-02 | Rejected: `publish date mismatch`. |
| 2025-03-01 | https://mp.weixin.qq.com/s/_kEYKZ60pUB-99lZA3tzpQ | 2026-03-01 | Rejected: `publish date mismatch`. |
| 2025-02-13 | https://mp.weixin.qq.com/s/dphjehVdeakcdnrrCjNFNA | 2026-02-13 | Rejected: `publish date mismatch`. |
| 2025-02-12 | https://mp.weixin.qq.com/s/fFvUhDalj03tNpm79ilCgA | 2026-02-12 | Rejected: `publish date mismatch`. |
| 2025-02-09 | https://mp.weixin.qq.com/s/ELjMADEyi9unlLzmN_mfXg | 2026-02-09 | Rejected: `publish date mismatch`. |
| 2025-02-03 | https://mp.weixin.qq.com/s/HWJiuILDwYBeV5X_erubwg | 2026-02-03 | Rejected: `publish date mismatch`. |
| 2025-02-02 | https://mp.weixin.qq.com/s/VP_Fk0hK1vrZn0AC9VJPHQ | 2026-02-02 | Rejected: `publish date mismatch`. |
| 2025-02-01 | https://mp.weixin.qq.com/s/tFkH3lx92lfUAm4lBLMk0A | 2026-02-01 | Rejected: `publish date mismatch`. |
| 2025-01-15 | https://mp.weixin.qq.com/s/U7Smdk2SuHUOefcmtGxfnA | 2026-01-15 | Rejected: `publish date mismatch`. |
| 2025-01-14 | https://mp.weixin.qq.com/s/UMw2vxPuNYqpSuDxdGgBzA | 2026-01-14 | Rejected: `publish date mismatch`. |
| 2025-01-13 | https://mp.weixin.qq.com/s/_WJaXxiT5t1F_E6zqdWDpQ | 2026-01-13 | Rejected: `publish date mismatch`. |

## Current Fetch Status

- `2025-md/` contains 188 accepted Markdown files.
- 2025-05-10 was recovered from account-scoped WeChat search as `https://mp.weixin.qq.com/s/BSIFLD5EKMuSsrGkcSDrPw`; HTML `ct` validates to 2025-05-10.
- 25 link records still need corrected 2025 URLs.
- The accepted Markdown files have no low-table/low-row failures; latest audit minimum was `tables=34`, `rows=376`.
- Latest parser summary after the fastpath run: `coreRecords=189`, `allPriceRows=47774`, `missingMarkdownDates=25`, `noProductDates=0`, `noCoreMaotaiDates=0`.
