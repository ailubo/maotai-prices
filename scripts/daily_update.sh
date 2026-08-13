#!/usr/bin/env bash
#
# daily_update.sh — 茅台批价每日更新的确定性顶层 runner（2026-08-12 建立）
#
# 封装: 抓专辑→验日期→抓正文→解析校验→重建报告→缺口核查→精确提交推送
# 输出机器可判状态行 STATUS=<state>（供自动化/上层明确分支，不再把"输出说明"当成功）
#
# 状态机:
#   DISCOVERY_FAILED        专辑页/最新文章抓取失败（基础设施故障）
#   VERIFIED_NOT_PUBLISHED  专辑可达且倒序成功，但最新文章日期 < 今天（今天的还没发布，正常跳过）
#   STALE_NO_PUBLISH        专辑可达，但最新文章日期落后 >= 2 天（异常，需人工核查）
#   FETCH_FAILED            正文抓取失败
#   PARSE_FAILED            解析/校验失败（未写任何数据）
#   ALREADY_EXISTS          当天数据已存在（幂等）
#   COMMIT_FAILED / PUSH_FAILED
#   SUCCESS                 完整更新成功
#
# 用法: bash scripts/daily_update.sh [--expect-date YYYY-MM-DD] [--skip-push]
#   --expect-date 默认今天；补录历史日期时传入目标日期
#   --skip-push   只更新数据不推送（调试用）

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(dirname "$SCRIPT_DIR")"
NODE_BIN="${NODE_BIN:-/Users/ailubo/.workbuddy/binaries/node/versions/22.22.2/bin/node}"
NODE_PATH="${NODE_PATH:-/Users/ailubo/.workbuddy/binaries/node/workspace/node_modules}"
BUN_BIN="/opt/homebrew/bin/bun"
BAOYU_CLI="/Users/ailubo/.workbuddy/skills/baoyu-url-to-markdown/scripts/lib/cli.ts"
PY_BIN="${PY_BIN:-/Users/ailubo/.workbuddy/binaries/python/versions/3.13.12/bin/python3}"

EXPECT_DATE="$(date +%F)"
SKIP_PUSH=0
for arg in "$@"; do
  case "$arg" in
    --expect-date=*) EXPECT_DATE="${arg#*=}" ;;
    --skip-push) SKIP_PUSH=1 ;;
  esac
done

OUT_STATUS=""
OUT_TITLE=""
OUT_LINK=""
OUT_DATE=""
OUT_SANPING=""
OUT_YUANXIANG=""

emit() {
  echo "STATUS=$OUT_STATUS"
  [[ -n "$OUT_TITLE" ]] && echo "ARTICLE_TITLE=$OUT_TITLE"
  [[ -n "$OUT_LINK" ]] && echo "ARTICLE_LINK=$OUT_LINK"
  [[ -n "$OUT_DATE" ]] && echo "ARTICLE_DATE=$OUT_DATE"
  [[ -n "$OUT_SANPING" ]] && echo "SANPING=$OUT_SANPING"
  [[ -n "$OUT_YUANXIANG" ]] && echo "YUANXIANG=$OUT_YUANXIANG"
}

fail() {  # fail <STATUS> <message>
  OUT_STATUS="$1"
  echo "ERR: $2" >&2
  emit
  exit 1
}

# ---------- 1. 发现: 专辑页最新文章 ----------
DISCOVERY_JSON="$(bash "$SCRIPT_DIR/fetch_latest_wechat_album_item.sh" 2>/tmp/daily_disc_err)"
if [[ $? -ne 0 ]]; then
  fail DISCOVERY_FAILED "专辑页抓取失败: $(head -3 /tmp/daily_disc_err)"
fi

OUT_TITLE="$(echo "$DISCOVERY_JSON" | "$PY_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("title",""))')"
OUT_LINK="$(echo "$DISCOVERY_JSON" | "$PY_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("link",""))')"

if [[ -z "$OUT_TITLE" || -z "$OUT_LINK" ]]; then
  fail DISCOVERY_FAILED "最新文章标题或链接为空"
fi

# 从标题解析日期 (2026年8月12日 / 8月12日 两种形态)
ARTICLE_DAY="$(echo "$OUT_TITLE" | "$PY_BIN" -c '
import re,sys
t=sys.stdin.read()
m=re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", t) or re.search(r"(\d{1,2})月(\d{1,2})日", t)
if not m: print(""); sys.exit()
if len(m.groups())==3: y,mo,d=m.groups()
else:
    mo,d=m.groups(); y="2026"
print(f"{y}-{int(mo):02d}-{int(d):02d}")
')"
OUT_DATE="$ARTICLE_DAY"

if [[ -z "$ARTICLE_DAY" ]]; then
  fail DISCOVERY_FAILED "无法从标题解析日期: $OUT_TITLE"
fi

# 日期判定
if [[ "$ARTICLE_DAY" < "$EXPECT_DATE" ]]; then
  LAG=$(( ($(date -j -f %Y-%m-%d "$EXPECT_DATE" +%s) - $(date -j -f %Y-%m-%d "$ARTICLE_DAY" +%s)) / 86400 ))
  if [[ "$LAG" -ge 2 ]]; then
    OUT_STATUS="STALE_NO_PUBLISH"
    echo "WARN: 最新文章日期 $ARTICLE_DAY 落后 $LAG 天 (期望 $EXPECT_DATE)，疑似多日未更新，需人工核查" >&2
    emit
    exit 0
  fi
  OUT_STATUS="VERIFIED_NOT_PUBLISHED"
  echo "INFO: 最新文章 ${ARTICLE_DAY}，今天(${EXPECT_DATE})文章尚未发布，正常跳过" >&2
  emit
  exit 0
fi
if [[ "$ARTICLE_DAY" > "$EXPECT_DATE" ]]; then
  fail DISCOVERY_FAILED "最新文章日期 $ARTICLE_DAY 晚于期望 $EXPECT_DATE（异常，疑似抓错或时区问题）"
fi

# ---------- 2. 抓正文 ----------
MD_PATH="/tmp/baoyu_daily_${EXPECT_DATE}.md"
"$BUN_BIN" "$BAOYU_CLI" "$OUT_LINK" --output "$MD_PATH" >/dev/null 2>/tmp/daily_fetch_err
if [[ $? -ne 0 || ! -s "$MD_PATH" ]]; then
  # Playwright 兜底直抓
  NODE_PATH="$NODE_PATH" "$NODE_BIN" "$SCRIPT_DIR/fetch_article_playwright.cjs" "$OUT_LINK" "$MD_PATH" >/dev/null 2>>/tmp/daily_fetch_err
  if [[ $? -ne 0 || ! -s "$MD_PATH" ]]; then
    fail FETCH_FAILED "正文抓取失败: $(tail -3 /tmp/daily_fetch_err)"
  fi
fi

# ---------- 3. 解析+硬校验 ----------
MAOTAI_MD_PATH="$MD_PATH" MAOTAI_EXPECT_DATE="$EXPECT_DATE" "$PY_BIN" "$SCRIPT_DIR/../parse_daily.py" >/tmp/daily_parse_out 2>/tmp/daily_parse_err
PARSE_EXIT=$?
if [[ $PARSE_EXIT -eq 2 ]]; then
  fail PARSE_FAILED "正文日期与期望不符: $(tail -2 /tmp/daily_parse_err)"
fi
if [[ $PARSE_EXIT -ne 0 ]]; then
  fail PARSE_FAILED "解析/校验失败: $(tail -2 /tmp/daily_parse_err)"
fi

if grep -q "already exists" /tmp/daily_parse_out; then
  OUT_STATUS="ALREADY_EXISTS"
  echo "INFO: $EXPECT_DATE 数据已存在，幂等跳过" >&2
  emit
  exit 0
fi

# macOS 原生 grep 不支持 -P（Perl 正则），改用 sed -E 提取散瓶/原箱数值
OUT_SANPING="$(sed -nE 's/.*散瓶: ([0-9]+).*/\1/p' /tmp/daily_parse_out | head -1)"
OUT_YUANXIANG="$(sed -nE 's/.*原箱: ([0-9]+).*/\1/p' /tmp/daily_parse_out | head -1)"

# ---------- 4. 重建报告 ----------
cd "$BASE" || fail VALIDATION_FAILED "无法进入项目目录"
"$PY_BIN" regenerate.py >/tmp/daily_regen_out 2>/tmp/daily_regen_err
if [[ $? -ne 0 ]]; then
  fail VALIDATION_FAILED "regenerate.py 失败: $(tail -3 /tmp/daily_regen_err)"
fi

# ---------- 5. 缺口核查 ----------
"$PY_BIN" "$SCRIPT_DIR/verify_data.py" --quiet --date "$EXPECT_DATE" >/tmp/daily_verify_out 2>&1
VERIFY_EXIT=$?
if [[ $VERIFY_EXIT -ne 0 ]]; then
  echo "WARN: 缺口核查发现异常: $(cat /tmp/daily_verify_out)" >&2
fi

# ---------- 6. 精确提交 + 推送 ----------
# regenerate.py 会重写全部月度 md（每个文件的"数据截止"行都更新），须暂存 2026/*.md 全部，
# 否则每月会残留 7 个未提交的月度文件（仅暂存当月会漏）。
git add data.json all_prices.jsonl 2026/*.md "2026总览.md" sources/ 2>/tmp/daily_git_err
if [[ $? -ne 0 ]]; then
  fail COMMIT_FAILED "git add 失败: $(tail -2 /tmp/daily_git_err)"
fi

if git diff --cached --quiet; then
  OUT_STATUS="ALREADY_EXISTS"
  echo "INFO: 无暂存变更（数据未变），跳过提交" >&2
  emit
  exit 0
fi

git commit -m "更新: ${EXPECT_DATE} 散=${OUT_SANPING:-?} 原=${OUT_YUANXIANG:-?}" >/tmp/daily_commit_out 2>/tmp/daily_commit_err
if [[ $? -ne 0 ]]; then
  fail COMMIT_FAILED "git commit 失败: $(tail -2 /tmp/daily_commit_err)"
fi

if [[ "$SKIP_PUSH" -eq 1 ]]; then
  OUT_STATUS="SUCCESS"
  echo "INFO: 已提交但 --skip-push 未推送" >&2
  emit
  exit 0
fi

git push origin main >/tmp/daily_push_out 2>/tmp/daily_push_err
if [[ $? -ne 0 ]]; then
  fail PUSH_FAILED "git push 失败: $(tail -2 /tmp/daily_push_err)"
fi

# 验证远端一致
git fetch origin main >/dev/null 2>&1
LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse origin/main)"
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  fail PUSH_FAILED "推送后 SHA 不一致: local=$LOCAL_SHA remote=$REMOTE_SHA"
fi

OUT_STATUS="SUCCESS"
emit
exit 0
