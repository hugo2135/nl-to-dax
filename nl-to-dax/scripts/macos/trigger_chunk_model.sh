#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
    echo "❌ 使用方式：bash trigger_chunk_model.sh <語意模型JSON檔案路徑>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/../shared/chunk_model.py" "$1"
