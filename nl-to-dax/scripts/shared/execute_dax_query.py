"""
Power BI REST API 執行端

用法: python execute_dax_query.py <ticket> <redeem_url> <workspace_id> <dataset_id> <dax_query_file> [output_csv_path]

**access token 全程不離開本行程的記憶體。** 呼叫端（Claude）只拿得到一次性 ticket，
由本腳本自己去兌換 token 再打 Power BI：

    ① POST <redeem_url>  {"ticket": ...}          → access_token（僅存在記憶體）
    ② POST api.powerbi.com/.../executeQueries     用 ① 的 token

這樣 token 不會進入對話上下文、不會出現在命令列、也不落地成檔案。
ticket 本身可以安全地當命令列參數傳遞——它是單次使用且短效（預設 300 秒），
兌換過或逾時即失效，就算外流價值也極低。

ticket 過期時（兌換回 401）會在 stdout 的 JSON 帶 `"ticket_expired": true`，
呼叫端據此重新呼叫 MCP 工具 `get_query_ticket` 取得新 ticket 後重跑即可——
腳本自己無法重取（它不能呼叫 MCP 工具）。這條路徑是必要的：Bash 執行前的
權限確認提示會把等待時間算進 ticket 效期內，使用者離開座位一下就會過期。

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


class TicketExpired(RuntimeError):
    """ticket 無效／已使用／已過期——呼叫端重新取得一張即可重試。"""


def redeem_ticket(redeem_url: str, ticket: str) -> str:
    """用一次性 ticket 兌換 access token。回傳值只在記憶體中流動，不寫出去。"""
    payload = json.dumps({"ticket": ticket}).encode('utf-8')
    req = urllib.request.Request(redeem_url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        if e.code == 401:
            raise TicketExpired("ticket 無效、已使用或已過期，需重新取得")
        if e.code == 403:
            raise RuntimeError("帳號已停用或 Azure AD 憑證已過期，請聯繫管理員")
        raise RuntimeError(f"ticket 兌換失敗 (HTTP {e.code}): {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"無法連線至 ticket 兌換端點：{e.reason}。"
            "若在 Claude Apps 沙盒中執行，請確認申請程式網域已加入 Network egress 白名單"
        )

    access_token = data.get('access_token')
    if not access_token:
        raise RuntimeError("兌換回應格式異常，缺少 access_token")
    return access_token


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
    if len(sys.argv) < 6:
        print(
            "用法: python execute_dax_query.py <ticket> <redeem_url> <workspace_id> "
            "<dataset_id> <dax_query_file> [output_csv_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    ticket = sys.argv[1]
    redeem_url = sys.argv[2]
    workspace_id = sys.argv[3]
    dataset_id = sys.argv[4]
    dax_file = sys.argv[5]
    csv_path = sys.argv[6] if len(sys.argv) > 6 else os.path.join("pbi_query", "query_result.csv")

    try:
        with open(dax_file, 'r', encoding='utf-8') as f:
            dax_query = f.read().strip()
        if not dax_query:
            raise RuntimeError(f"DAX 查詢檔案為空：{dax_file}")

        print("兌換 ticket...", file=sys.stderr)
        access_token = redeem_ticket(redeem_url, ticket)

        print("執行 DAX 查詢...", file=sys.stderr)
        result = execute_dax(access_token, workspace_id, dataset_id, dax_query)
        del access_token

        csv_content, row_count = result_to_csv(result)

        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(csv_content)

        print(f"完成，共 {row_count} 筆資料 → {csv_path}", file=sys.stderr)
        print(json.dumps({"success": True, "row_count": row_count, "csv_path": csv_path}))

    except TicketExpired as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "ticket_expired": True, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
