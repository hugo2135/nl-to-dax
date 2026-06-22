#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ] || [ -z "${2:-}" ]; then
    echo "❌ 使用方式：bash trigger_pbi_api.sh <jwt_config_path> <dax_query_file> [output_csv_path]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# skill root = scripts/ 的上一層
SKILL_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# 往上找到包含 .claude/ 的目錄作為工作區根目錄
WORKSPACE_ROOT="$SCRIPT_DIR"
while [ "$WORKSPACE_ROOT" != "/" ]; do
    [ -d "$WORKSPACE_ROOT/.claude" ] && break
    WORKSPACE_ROOT="$(dirname "$WORKSPACE_ROOT")"
done
PBI_QUERY_DIR="$WORKSPACE_ROOT/pbi_query"
mkdir -p "$PBI_QUERY_DIR"

CONFIG_PATH="${1:-$SKILL_ROOT/config/pbi_credentials.jwt}"
DAX_QUERY_FILE="$2"
OUTPUT_CSV="${3:-$PBI_QUERY_DIR/query_result.csv}"

python3 "$SCRIPT_DIR/../shared/pbi_api_client.py" "$CONFIG_PATH" "$DAX_QUERY_FILE" "$OUTPUT_CSV"
