#!/usr/bin/env bash
#
# 获取今日酒价公众号专辑页最新文章 (title + data-link)
#
# 输出: 默认 JSON 对象 {title, link}；传入篇数时输出倒序 JSON 数组。
# 退出码: 0=成功, 1=失败, 75=已有任务在运行(并发跳过)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCH="$SCRIPT_DIR/../../wechat-article-fetcher/scripts/fetch_wechat_ego.py"
ALBUM_URL='https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect'
TASK_LOCK_DIR="${TASK_LOCK_DIR:-${TMPDIR:-/tmp}/maotai-daily-playwright.lock}"
TASK_LOCK_EMPTY_STALE_SECONDS="${TASK_LOCK_EMPTY_STALE_SECONDS:-60}"
TASK_LOCK_HELD=0

acquire_task_lock() {
  local attempt
  local lock_age=0
  local lock_mtime=0
  local now=0
  local owner_pid=""

  for attempt in 1 2; do
    if mkdir "$TASK_LOCK_DIR" 2>/dev/null; then
      printf '%s\n' "$$" >"$TASK_LOCK_DIR/owner-pid"
      TASK_LOCK_HELD=1
      return 0
    fi

    if [[ -r "$TASK_LOCK_DIR/owner-pid" ]]; then
      owner_pid="$(<"$TASK_LOCK_DIR/owner-pid")"
    fi
    if [[ "$owner_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$owner_pid" 2>/dev/null; then
      rm -f "$TASK_LOCK_DIR/owner-pid"
      rmdir "$TASK_LOCK_DIR" 2>/dev/null || true
      owner_pid=""
      continue
    fi

    if [[ ! "$owner_pid" =~ ^[0-9]+$ ]]; then
      lock_mtime="$(stat -f '%m' "$TASK_LOCK_DIR/owner-pid" 2>/dev/null || stat -f '%m' "$TASK_LOCK_DIR" 2>/dev/null || printf '0')"
      now="$(date +%s)"
      if [[ "$lock_mtime" =~ ^[0-9]+$ ]]; then
        lock_age=$((now - lock_mtime))
      fi
      if (( lock_age >= TASK_LOCK_EMPTY_STALE_SECONDS )); then
        rm -f "$TASK_LOCK_DIR/owner-pid"
        rmdir "$TASK_LOCK_DIR" 2>/dev/null || true
        if [[ ! -e "$TASK_LOCK_DIR" ]]; then
          owner_pid=""
          continue
        fi
      fi
    fi

    echo "已有茅台批价浏览器任务在运行，拒绝并发启动：$TASK_LOCK_DIR" >&2
    return 75
  done

  echo "无法取得茅台批价浏览器任务锁：$TASK_LOCK_DIR" >&2
  return 75
}

release_task_lock() {
  local owner_pid=""
  if [[ "$TASK_LOCK_HELD" -ne 1 ]]; then
    return 0
  fi
  if [[ -r "$TASK_LOCK_DIR/owner-pid" ]]; then
    owner_pid="$(<"$TASK_LOCK_DIR/owner-pid")"
  fi
  if [[ "$owner_pid" == "$$" ]]; then
    rm -f "$TASK_LOCK_DIR/owner-pid"
    rmdir "$TASK_LOCK_DIR" 2>/dev/null || true
  fi
  TASK_LOCK_HELD=0
}

cleanup() {
  local task_exit_code=$?
  trap - EXIT INT TERM
  release_task_lock
  exit "$task_exit_code"
}

acquire_task_lock
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# 采集 JSON 只走 stdout，错误走 stderr，供上层区分未发布和发现失败。
entries="$(/usr/bin/python3 "$FETCH" album "$ALBUM_URL" --limit "${1:-1}")"
if [[ $# -eq 0 ]]; then
  /usr/bin/python3 -c 'import json, sys; print(json.dumps(json.load(sys.stdin)[0], ensure_ascii=False))' <<<"$entries"
else
  printf '%s\n' "$entries"
fi
