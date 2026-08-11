"""
Power BI REST API 執行端

用法: python execute_dax_query.py <token_file> <workspace_id> <dataset_id> <dax_query_file> [output_csv_path]

access_token 透過**檔案**傳入，不走命令列參數。原因：
- 命令列內容同機其他行程可讀（Windows `wmic process get commandline`、工作管理員的
  命令列欄位；Linux `/proc/<pid>/cmdline`），且可能被寫進 shell 歷史檔
- 呼叫端 UI 會完整顯示待執行的指令，近 2000 字元的 JWT 會把版面灌爆

token 檔由呼叫端（Claude）用 MCP 工具 `get_powerbi_token` 取得後寫入，
本腳本**讀取後立即刪除**（即使後續查詢失敗也一定刪除），不快取、不跨對話保留。

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


def _consume_token_file(token_file: str) -> str:
    """讀出 token 後立即刪除該檔案。

    用 try/finally 確保「讀取失敗」與「檔案內容為空」等情況下也會刪除，
    不讓 token 因為任何錯誤路徑而殘留在磁碟上。
    """
    try:
        with open(token_file, 'r', encoding='utf-8') as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"找不到 token 檔案：{token_file}")
    finally:
        try:
            os.remove(token_file)
        except OSError:
            pass

    if not token:
        raise RuntimeError(f"token 檔案內容為空：{token_file}")
    return token


def main():
    if len(sys.argv) < 5:
        print(
            "用法: python execute_dax_query.py <token_file> <workspace_id> <dataset_id> <dax_query_file> [output_csv_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    token_file = sys.argv[1]
    workspace_id = sys.argv[2]
    dataset_id = sys.argv[3]
    dax_file = sys.argv[4]
    csv_path = sys.argv[5] if len(sys.argv) > 5 else os.path.join("pbi_query", "query_result.csv")

    try:
        # 最先執行：不論後續成功與否，token 檔都已經被刪除。
        access_token = _consume_token_file(token_file)

        with open(dax_file, 'r', encoding='utf-8') as f:
            dax_query = f.read().strip()
        if not dax_query:
            raise RuntimeError(f"DAX 查詢檔案為空：{dax_file}")

        print("執行 DAX 查詢...", file=sys.stderr)
        result = execute_dax(access_token, workspace_id, dataset_id, dax_query)
        del access_token

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
