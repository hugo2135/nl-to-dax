#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ] || [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
    echo "❌ 使用方式：bash trigger_pbi_api.sh <workspace_root> <pbi_config_id> <dax_query_file> [output_csv_path]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKSPACE_ROOT="$1"
PBI_QUERY_DIR="$WORKSPACE_ROOT/pbi_query"
mkdir -p "$PBI_QUERY_DIR"

PBI_CONFIG_ID="$2"
DAX_QUERY_FILE="$3"
OUTPUT_CSV="${4:-$PBI_QUERY_DIR/query_result.csv}"

python3 "$SCRIPT_DIR/../shared/pbi_api_client.py" "$WORKSPACE_ROOT" "$PBI_CONFIG_ID" "$DAX_QUERY_FILE" "$OUTPUT_CSV"
