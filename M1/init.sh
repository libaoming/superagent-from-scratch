#!/bin/bash
# M1/init.sh — 环境自检（6 段，走完统一报告，不用 set -e）
# fixture 缺失只 WARN，依赖/env 缺失记 FAIL。

WARN=0; FAIL=0
ok(){ echo "  ✅ $1"; }
warn(){ echo "  ⚠️  $1"; WARN=$((WARN+1)); }
fail(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "== 1. 依赖 =="
# command -v python3 >/dev/null && ok "python3" || fail "python3 缺失"

echo "== 2. env =="
# [ -f .env ] && ok ".env 存在" || warn ".env 缺失（看 .env.example）"

echo "== 3. 外部服务 =="
# 探活 DB / Redis / 远程 API（按项目补）

echo "== 4. schema =="
# [ -f features.json ] && python3 -c "import json;json.load(open('features.json'))" 2>/dev/null && ok "features.json 合法" || fail "features.json 非法"

echo "== 5. fixtures =="
# [ -d fixtures ] && ok "fixtures/ 存在" || warn "fixtures/ 缺失"

echo "== 6. 端到端 =="
# 最小冒烟（按项目补）

echo ""
echo "== 自检结果：FAIL=$FAIL WARN=$WARN =="
[ "$FAIL" -gt 0 ] && echo "🔴 有阻塞项，先修 FAIL 再开工" || echo "🟢 可开工（WARN 不阻塞）"
