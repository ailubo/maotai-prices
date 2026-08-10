#!/usr/bin/env bash

set -euo pipefail

AGENT_BROWSER_BIN="${AGENT_BROWSER_BIN:-/Users/ailubo/.workbuddy/binaries/node/versions/22.22.2/bin/agent-browser}"
AGENT_BROWSER_SESSION="${AGENT_BROWSER_SESSION:-maotai-daily}"
AGENT_BROWSER_PROXY="${AGENT_BROWSER_PROXY:-http://127.0.0.1:7897}"
ALBUM_URL="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect"
TASK_LOCK_DIR="${TASK_LOCK_DIR:-${TMPDIR:-/tmp}/maotai-daily-agent-browser.lock}"
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

    # A SIGKILL or power loss can occur between mkdir and writing owner-pid.
    # Do not reclaim a fresh empty/malformed lock because another process may
    # still be creating it; only recover it after a conservative grace period.
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

session_is_active() {
  local session_line="  $AGENT_BROWSER_SESSION"

  "$AGENT_BROWSER_BIN" session list 2>/dev/null | grep -Fqx "$session_line"
}

close_browser_session() {
  local attempt

  # Repeat close until the session is absent in two consecutive checks. A
  # failed navigation can finish registering the session after the first close.
  for attempt in {1..20}; do
    "$AGENT_BROWSER_BIN" --session "$AGENT_BROWSER_SESSION" close >/dev/null 2>&1 || true
    sleep 0.1
    if ! session_is_active; then
      sleep 0.1
      if ! session_is_active; then
        return 0
      fi
    fi
  done

  echo "未能关闭 agent-browser 会话：$AGENT_BROWSER_SESSION" >&2
  return 1
}

close_stale_browser_session() {
  if session_is_active; then
    close_browser_session
  fi
}

cleanup() {
  local task_exit_code=$?
  local cleanup_failed=0

  trap - EXIT INT TERM
  if ! close_browser_session; then
    cleanup_failed=1
  fi
  release_task_lock

  if [[ "$cleanup_failed" -ne 0 && "$task_exit_code" -eq 0 ]]; then
    task_exit_code=70
  fi
  exit "$task_exit_code"
}

browser() {
  "$AGENT_BROWSER_BIN" \
    --session "$AGENT_BROWSER_SESSION" \
    "$@"
}

browser_open() {
  "$AGENT_BROWSER_BIN" \
    --session "$AGENT_BROWSER_SESSION" \
    --proxy "$AGENT_BROWSER_PROXY" \
    open "$1"
}

# Close a stale session from a previously interrupted run, then guarantee that
# this run releases Chrome even when a browser command fails or the shell exits.
acquire_task_lock
close_stale_browser_session
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

browser_open "$ALBUM_URL" >/dev/null
browser wait --load networkidle >/dev/null 2>&1 || browser wait 3000 >/dev/null

browser eval '(() => {
  const node = document.evaluate(
    "//*[normalize-space(text())=\"倒序\"]",
    document,
    null,
    XPathResult.FIRST_ORDERED_NODE_TYPE,
    null
  ).singleNodeValue;
  if (!node) throw new Error("找不到倒序按钮");
  (node.parentElement || node).click();
  return true;
})()' >/dev/null

browser wait 3000 >/dev/null
browser eval '(() => {
  const item = document.querySelector(".album__list-item");
  if (!item) throw new Error("找不到专辑文章");
  const title = item.getAttribute("data-title") || item.dataset.title || "";
  const link = item.getAttribute("data-link") || item.dataset.link || "";
  if (!link) throw new Error("第一篇文章缺少 data-link");
  return { title, link };
})()'
