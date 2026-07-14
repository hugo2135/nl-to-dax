#!/bin/bash
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "❌ 使用方式：bash trigger_model_overview.sh <workspace_root> <pbi_config_id>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/../shared/model_overview.py" "$1" "$2"
