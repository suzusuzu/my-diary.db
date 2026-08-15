#!/bin/bash
# このリポジトリは core.hooksPath = git-hooks で pre-commit を参照する。
# core.hooksPath はローカル git config なので、クローンした他マシンには
# 伝搬しない。新マシンではこのスクリプトを一度実行して hooks を有効化する。
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

git config core.hooksPath git-hooks
chmod +x git-hooks/pre-commit tools/export_csv.py tools/jst_now.py setup-hooks.sh

# venv が無ければ自動作成（matplotlib 等は無くても CSV 生成は python3 で動く）
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
fi

echo "hooks 有効化済み (core.hooksPath=git-hooks)"
git config --get core.hooksPath
