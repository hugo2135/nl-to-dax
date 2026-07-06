#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ] || [ -z "${2:-}" ]; then
    echo "❌ 使用方式：bash trigger_pbi_api.sh <pbi_config_id> <dax_query_file> [output_csv_path]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 往上找到包含 .claude/ 的目錄作為工作區根目錄
WORKSPACE_ROOT="$SCRIPT_DIR"
while [ "$WORKSPACE_ROOT" != "/" ]; do
    [ -d "$WORKSPACE_ROOT/.claude" ] && break
    WORKSPACE_ROOT="$(dirname "$WORKSPACE_ROOT")"
done
PBI_QUERY_DIR="$WORKSPACE_ROOT/pbi_query"
mkdir -p "$PBI_QUERY_DIR"

PBI_CONFIG_ID="$1"
DAX_QUERY_FILE="$2"
OUTPUT_CSV="${3:-$PBI_QUERY_DIR/query_result.csv}"

python3 "$SCRIPT_DIR/../shared/pbi_api_client.py" "$PBI_CONFIG_ID" "$DAX_QUERY_FILE" "$OUTPUT_CSV"
