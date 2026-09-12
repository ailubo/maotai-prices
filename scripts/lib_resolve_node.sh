#!/usr/bin/env bash
#
# lib_resolve_node.sh — 托管 Node 运行时可执行文件的动态解析（2026-09-12 建立）
#
# 背景（2026-09-12 事故）:
#   宿主会重新版本化托管运行时目录 ~/.workbuddy/binaries/node/versions/<ver>
#   （2026-09-11 17:09 由 22.22.2-2 变为 22.22.2-3）。此前 daily_update.sh 与
#   fetch_latest_wechat_album_item.sh 硬编码了版本号，宿主升级后 NODE_BIN 指向
#   不存在的路径 → node 调用 exit 127 → STATUS=DISCOVERY_FAILED。
#   故改为动态解析，宿主再升级运行时无需改脚本。
#
# 解析优先级:
#   1) 环境变量 NODE_BIN —— 显式覆盖，保留给排障与测试（调用方先判断，本函数不读）
#   2) versions/current —— 宿主维护的版本指针；可为软链，也可为内含版本号的普通文件
#   3) versions/ 下 mtime 最新的目录（取其 bin/node）
#   4) PATH 中的 node（command -v node）
#   全部失败则输出空字符串，由调用方判定并给出明确报错（不静默）。
#
# 依赖: 仅 bash 内建 + ls/tr/readlink/command。使用显式 if（避免 set -e 下
#       `[[ ]] && cmd` 的 AND-OR 退出码陷阱）。

# 允许测试时用 MAOTAI_NODE_VERSIONS_DIR 指向假目录
resolve_node_bin() {
  local base="${MAOTAI_NODE_VERSIONS_DIR:-$HOME/.workbuddy/binaries/node/versions}"
  local cand=""

  # (2.1) versions/current 为软链
  if [[ -L "$base/current" ]]; then
    local target=""
    target="$(cd "$base" 2>/dev/null && readlink current 2>/dev/null)" || target=""
    if [[ -n "$target" && "$target" != /* ]]; then
      target="$base/$target"
    fi
    if [[ -n "$target" && -x "$target/bin/node" ]]; then
      cand="$target/bin/node"
    fi
  fi

  # (2.2) versions/current 为普通文件（内含版本号）
  if [[ -z "$cand" && -f "$base/current" ]]; then
    local ver=""
    ver="$(tr -d '[:space:]' <"$base/current" 2>/dev/null)" || ver=""
    if [[ -n "$ver" && -x "$base/$ver/bin/node" ]]; then
      cand="$base/$ver/bin/node"
    fi
  fi

  # (3) versions/ 下按 mtime 取最新的可用 node（ls -dt 最新在最前）
  if [[ -z "$cand" && -d "$base" ]]; then
    local d=""
    while IFS= read -r d; do
      d="${d%/}"   # ls -dt 输出带结尾斜杠，去掉以免产生 // 双斜杠路径
      if [[ -n "$d" && -x "$d/bin/node" ]]; then
        cand="$d/bin/node"
      fi
      break
    done < <(ls -dt "$base"/*/ 2>/dev/null)
  fi

  # (4) PATH 兜底
  if [[ -z "$cand" ]]; then
    cand="$(command -v node 2>/dev/null)" || cand=""
  fi

  printf '%s' "$cand"
}
