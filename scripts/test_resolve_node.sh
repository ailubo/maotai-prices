#!/usr/bin/env bash
#
# test_resolve_node.sh — lib_resolve_node.sh 的回归测试（2026-09-12 建立）
#
# 为什么要有它：2026-09-12 的修复（动态解析）当初只做了一次性验证，
# 用例跑在会话里、**没有落盘**，下次无法复验。按 codex-audit 的既有约定
# 「修复必须带可复现测试入库，否则判『测试未入库』不放行」，本文件补齐。
#
# 用法: bash scripts/test_resolve_node.sh        # 期望输出 ALL PASS，退出码 0
#
# 设计要点：全部用**隔离的假 versions 目录**（mktemp），不碰真实运行时目录。
# 🔴 关键：**判别用例**（构造为「该分支失效时结果会不同」）——T2/T3/T8/T10/T12/T14/T16/T17/T18/T19。
#    否则测试全绿也可能是全程没走到那条路径
#    （2026-09-12 的教训：真机只有一个版本目录，第2层失效后第3层按 mtime
#      兜底恰好返回同一路径，掩盖了回归）。
# 陪跑用例（有价值但不具判别力，仅防崩溃/防退化）：T1/T4/T5/T6/T7/T9/T11/T13/T15。
set -uo pipefail

LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_resolve_node.sh"
[ -r "$LIB" ] || { echo "找不到 $LIB" >&2; exit 2; }

TMPROOT="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/test_resolve_node.XXXXXXXX")" || exit 2
trap '/bin/rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
pass() { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n        期望=[%s]\n        实得=[%s]\n' "$1" "$2" "$3"; }
eq()   { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1" "$2" "$3"; fi; }

# 造一个带可执行 bin/node 的假版本目录
mknode() {
  /bin/mkdir -p "$1/bin" || return 1
  printf '#!/bin/sh\necho %s\n' "$(/usr/bin/basename "$1")" > "$1/bin/node"
  /bin/chmod +x "$1/bin/node"
}
# 新假 versions 基目录
newbase() { local d="$TMPROOT/$1"; /bin/mkdir -p "$d"; printf '%s' "$d"; }
# 在受控环境里跑解析器；$2 可选，覆盖 PATH（该分支刻意吞 stderr：
# PATH 被故意打断时外层 shell 运行时 shim 会报错，与被测逻辑无关，属噪音）
resolve_in() {
  if [ -n "${2:-}" ]; then
    MAOTAI_NODE_VERSIONS_DIR="$1" PATH="$2" /bin/bash -c 'source "$1"; resolve_node_bin' _ "$LIB" 2>/dev/null
  else
    MAOTAI_NODE_VERSIONS_DIR="$1" /bin/bash -c 'source "$1"; resolve_node_bin' _ "$LIB"
  fi
}
echo "lib: $LIB"

# ---- T1 真环境（不覆盖 base）：解析结果必须存在且可执行 ----
r="$(/bin/bash -c 'source "$1"; resolve_node_bin' _ "$LIB")"
if [ -n "$r" ] && [ -x "$r" ]; then pass "T1 真环境解析出可执行 node"
else fail "T1 真环境解析出可执行 node" "非空且可执行" "$r"; fi

# ---- T2 current 为普通文件（带换行）→ 命中它，而非 mtime 更新的诱饵 ----
b="$(newbase t2)"; mknode "$b/verA"; mknode "$b/verB"
printf 'verA\n' > "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T2 current 普通文件优先于 mtime" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T3 current 为软链 → 命中它，而非 mtime 更新的诱饵 ----
b="$(newbase t3)"; mknode "$b/verA"; mknode "$b/verB"
/bin/ln -s verA "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T3 current 软链优先于 mtime" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T4 无 current → 取 mtime 最新者 ----
b="$(newbase t4)"; mknode "$b/verA"; mknode "$b/verB"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T4 无 current 取 mtime 最新" "$b/verB/bin/node" "$(resolve_in "$b")"

# ---- T5 current 指向不存在的版本 → 回退第3层 ----
b="$(newbase t5)"; mknode "$b/verA"
printf 'verGone\n' > "$b/current"
eq "T5 current 指向失效版本时回退" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T6 base 不存在 → 落 PATH ----
r="$(resolve_in "$TMPROOT/t6_does_not_exist")"
if [ -n "$r" ] && [ -x "$r" ]; then pass "T6 base 不存在时落 PATH"
else fail "T6 base 不存在时落 PATH" "非空且可执行" "$r"; fi

# ---- T7 base 无可用版本 + PATH 无 node → 返回空且**退出码为 0** ----
# 🔴 必须同时断言退出码（Codex 第5轮 P2）：只比 stdout 是否为空的话，"解析器异常退出"
#    也会被算成通过。且不能把整个 PATH 打断——那会连 ls/readlink 一起弄没，还会引来
#    外层 shell 运行时 shim 的报错。改用「工具齐备、独缺 node」的受控 PATH。
CTRLBIN="$TMPROOT/t7_bin"; /bin/mkdir -p "$CTRLBIN"
for t in ls readlink cat tr dirname basename mkdir chmod awk stat grep sed printf; do
  if [ -x "/bin/$t" ] && [ ! -e "$CTRLBIN/$t" ]; then /bin/ln -s "/bin/$t" "$CTRLBIN/$t"; fi
  if [ -x "/usr/bin/$t" ] && [ ! -e "$CTRLBIN/$t" ]; then /bin/ln -s "/usr/bin/$t" "$CTRLBIN/$t"; fi
done
b="$(newbase t7)"; /bin/mkdir -p "$b/verA"   # 只有目录、无 bin/node
out7="$(MAOTAI_NODE_VERSIONS_DIR="$b" PATH="$CTRLBIN" /bin/bash -c 'source "$1"; resolve_node_bin' _ "$LIB" 2>/dev/null)"; rc7=$?
if [ "$rc7" -eq 0 ] && [ -z "$out7" ]; then pass "T7 全部失败应返回空且退出码 0"
else fail "T7 全部失败应返回空且退出码 0" "rc=0 且输出为空" "rc=$rc7 out=[$out7]"; fi

# ---- T8 current 含多行 → 只取首行，不拼接成别的版本名 ----
b="$(newbase t8)"; mknode "$b/verA"; mknode "$b/verB"
printf 'verA\nverB\n' > "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T8 current 多行只取首行" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T9 current 普通文件含 ../ → 拒绝该层，不越界 ----
b="$(newbase t9)"; mknode "$b/verA"; ev="$TMPROOT/t9_evil"; mknode "$ev"
printf '../t9_evil\n' > "$b/current"
eq "T9 current 含 ../ 被拒" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T10 current 软链目标含 .. → 拒绝该层，不越界 ----
# 🔴 2026-09-12 写入本用例时**直接跑红**，暴露一个真实缺陷：
#    层2.1 把 target 置空后，层3 `ls -dt "$base"/*/` 会把 `current` 这个**指向目录的软链**
#    当作普通目录重新枚举回来（`-x "$base/current/bin/node"` 穿透软链命中），
#    ⇒ 层2.1 的 `..` 拒绝被**完全旁路**，该「输入规范化」实际无效。
#    本用例即该缺陷的判别用例（修复前失败、修复后通过）。
b="$(newbase t10)"; mknode "$b/verA"; ev="$TMPROOT/t10_evil"; mknode "$ev"
/bin/ln -s ../t10_evil "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/current"
eq "T10 current 软链含 .. 被拒（层3 不得把软链目录收回）" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T11 HOME 未定义 + set -u → 不得中断，落 PATH ----
r="$(/usr/bin/env -u HOME /bin/bash -c 'set -u; source "$1"; resolve_node_bin' _ "$LIB" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 0 ] && [ -n "$r" ] && [ -x "$r" ]; then pass "T11 HOME 未定义时落 PATH 不中断"
else fail "T11 HOME 未定义时落 PATH 不中断" "exit=0 且可执行" "exit=$rc out=$r"; fi

# ---- T12 第3层 break 位置：mtime 最新目录无 bin/node → 取次新可用者 ----
b="$(newbase t12)"; /bin/mkdir -p "$b/verEmpty"; mknode "$b/verGood"
/usr/bin/touch -t 202001010000 "$b/verGood"; /usr/bin/touch -t 209901010000 "$b/verEmpty"
eq "T12 最新目录无 node 时取次新可用" "$b/verGood/bin/node" "$(resolve_in "$b")"

# ---- T13 current 含首尾空白 → trim 后命中 ----
b="$(newbase t13)"; mknode "$b/verA"; mknode "$b/verB"
printf '  verA  \n' > "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T13 current 首尾空白被 trim" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T14 🔴 判别用例（read 遇 EOF 无换行回归）：current 无末尾换行且指向较旧目录 ----
b="$(newbase t14)"; mknode "$b/verOld"; mknode "$b/verNew"
printf 'verOld' > "$b/current"   # 无末尾换行（真机 current 正是这种 9 字节形态）
/usr/bin/touch -t 202001010000 "$b/verOld"; /usr/bin/touch -t 209901010000 "$b/verNew"
eq "T14 current 无末尾换行仍生效（不落 mtime 兜底）" "$b/verOld/bin/node" "$(resolve_in "$b")"

# ---- T15 current 无末尾换行（单版本，事故原始形态）----
b="$(newbase t15)"; mknode "$b/verA"
printf 'verA' > "$b/current"
eq "T15 current 无末尾换行（单版本）" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T16 current 含 CRLF → rtrim 去掉 \r 后命中 ----
b="$(newbase t16)"; mknode "$b/verA"; mknode "$b/verB"
printf 'verA\r\n' > "$b/current"
/usr/bin/touch -t 202001010000 "$b/verA"; /usr/bin/touch -t 209901010000 "$b/verB"
eq "T16 current 含 CRLF 被 trim" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T17 版本目录**本身是软链** → 层3 仍应采纳（不得静默退回 PATH 的另一个 node）----
# 🔴 判别用例：它能区分「只排除 current」与「粗暴跳过所有软链」两种实现。
#    后者会让宿主的软链版本目录不可用、静默落到 PATH —— 正是本次事故要消灭的静默失败。
b="$(newbase t17)"; real="$TMPROOT/t17_real"; mknode "$real"
/bin/ln -s "$real" "$b/verLink"
/usr/bin/touch -t 202001010000 "$real"
eq "T17 版本目录为软链仍被层3 采纳" "$b/verLink/bin/node" "$(resolve_in "$b")"

# ---- T18 current 是软链（指向 versions 之外一个含版本号的普通文件）→ 层2.2 不得跟随 ----
# 🔴 判别用例：跟随就会把「层2.1 刚拒绝掉的软链」在层2.2 又读回来（跨层接受路径）。
b="$(newbase t18)"; mknode "$b/verA"; mknode "$b/verB"
/usr/bin/touch -t 202001010000 "$b/verB"; /usr/bin/touch -t 209901010000 "$b/verA"
ptr="$TMPROOT/t18_ptr"; printf 'verB\n' > "$ptr"
/bin/ln -s "$ptr" "$b/current"
eq "T18 层2.2 不得跟随软链 current" "$b/verA/bin/node" "$(resolve_in "$b")"

# ---- T19 最新目录的 bin/node 存在但**不可执行** → 跳过，取次新可执行者 ----
b="$(newbase t19)"; /bin/mkdir -p "$b/verNoX/bin"
printf '#!/bin/sh\n' > "$b/verNoX/bin/node"; /bin/chmod 0644 "$b/verNoX/bin/node"
mknode "$b/verGood"
/usr/bin/touch -t 202001010000 "$b/verGood"; /usr/bin/touch -t 209901010000 "$b/verNoX"
eq "T19 不可执行候选被跳过" "$b/verGood/bin/node" "$(resolve_in "$b")"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS  ($PASS/$((PASS + FAIL)))"
  exit 0
fi
echo "FAILED  ($FAIL 项失败 / 共 $((PASS + FAIL)))"
exit 1
