"""
Power BI REST API 執行端

用法: python execute_dax_query.py <access_token> <workspace_id> <dataset_id> <dax_query_file> [output_csv_path]

access_token 由呼叫端（Claude）透過 MCP 工具 get_powerbi_token 取得後傳入，
本腳本不快取、不落地儲存任何 token，執行完即結束。

stdout: JSON 摘要  {"success": true, "row_count": N, "csv_path": "..."}
stderr: 執行進度與錯誤訊息
"""

import sys
import json
import os
import csv
import io
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def execute_dax(access_token: str, workspace_id: str, dataset_id: str, dax_query: str) -> dict:
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
        f"/datasets/{dataset_id}/executeQueries"
    )
    payload = json.dumps({
        "queries": [{"query": dax_query}],
        "serializerSettings": {"includeNulls": True},
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Authorization', f'Bearer {access_token}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Power BI API 查詢失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")


def result_to_csv(result: dict) -> tuple[str, int]:
    """回傳 (csv_string, row_count)"""
    try:
        table = result['results'][0]['tables'][0]
        rows_data = table.get('rows', [])

        if 'columns' in table:
            columns = [col['name'] for col in table['columns']]
        elif rows_data:
            columns = list(rows_data[0].keys())
        else:
            columns = []

        rows = [
            [row.get(col, '') for col in columns]
            for row in rows_data
        ]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"API 回傳格式異常，無法轉換為 CSV：{e}\n完整回應：{json.dumps(result, ensure_ascii=False)}")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)
    return output.getvalue(), len(rows)


def main():
    if len(sys.argv) < 5:
        print(
            "用法: python execute_dax_query.py <access_token> <workspace_id> <dataset_id> <dax_query_file> [output_csv_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    access_token = sys.argv[1]
    workspace_id = sys.argv[2]
    dataset_id = sys.argv[3]
    dax_file = sys.argv[4]
    csv_path = sys.argv[5] if len(sys.argv) > 5 else os.path.join("pbi_query", "query_result.csv")

    try:
        with open(dax_file, 'r', encoding='utf-8') as f:
            dax_query = f.read().strip()
        if not dax_query:
            raise RuntimeError(f"DAX 查詢檔案為空：{dax_file}")

        print("執行 DAX 查詢...", file=sys.stderr)
        result = execute_dax(access_token, workspace_id, dataset_id, dax_query)

        csv_content, row_count = result_to_csv(result)

        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(csv_content)

        print(f"完成，共 {row_count} 筆資料 → {csv_path}", file=sys.stderr)
        print(json.dumps({"success": True, "row_count": row_count, "csv_path": csv_path}))

    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
