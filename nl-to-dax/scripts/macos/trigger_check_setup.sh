#!/bin/bash
if [ -z "$1" ]; then
    echo "❌ 使用方式：bash trigger_check_setup.sh <workspace_root>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/../shared/check_setup.py" "$1"
