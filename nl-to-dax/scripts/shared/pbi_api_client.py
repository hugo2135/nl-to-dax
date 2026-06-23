#!/usr/bin/env python3
"""
Power BI REST API 客戶端

用法: python pbi_api_client.py <jwt_config_path> <dax_query_file> [output_csv_path]

環境變數:
  PBI_MASK_KEY  用於驗證 JWT 設定檔的 HS256 簽名金鑰（由供應方提供）

stdout: JSON 摘要  {"success": true, "row_count": N, "csv_path": "..."}
stderr: 執行進度與錯誤訊息
"""

import sys
import json
import os
import base64
import hmac
import hashlib
import time
import csv
import io
import urllib.request
import urllib.parse
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


# ── Workspace root ────────────────────────────────────────────────────────────

def _find_workspace_root(start_dir: str) -> str:
    """往上找到包含 .claude/ 的目錄，即工作區根目錄。"""
    current = start_dir
    while True:
        if os.path.isdir(os.path.join(current, ".claude")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("找不到工作區根目錄（未找到 .claude 資料夾）")
        current = parent


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _b64url_decode(s: str) -> bytes:
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _decode_jwt(token: str, secret: str) -> dict:
    parts = token.strip().split('.')
    if len(parts) != 3:
        raise ValueError("無效的 JWT 格式（需要三個以 '.' 分隔的部分）")

    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()
    actual = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected, actual):
        raise ValueError("JWT 簽名驗證失敗：PBI_MASK_KEY 不符，或設定檔已遭篡改")

    payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))

    if 'exp' in payload and payload['exp'] < time.time():
        exp_date = time.strftime('%Y-%m-%d', time.localtime(payload['exp']))
        raise ValueError(f"設定檔 JWT 已於 {exp_date} 過期，請向供應方申請更新")

    return payload


# ── Credentials ───────────────────────────────────────────────────────────────

def load_credentials(jwt_path: str) -> dict:
    server_secret = os.environ.get('SERVER_JWT_SECRET')
    if not server_secret:
        raise RuntimeError(
            "環境變數 SERVER_JWT_SECRET 未設定。\n"
            "請向管理員取得後設定：\n"
            "  Windows: $env:SERVER_JWT_SECRET = \"your-key\"\n"
            "  macOS/Linux: export SERVER_JWT_SECRET=\"your-key\""
        )

    with open(jwt_path, 'r', encoding='utf-8') as f:
        token = f.read().strip()

    payload = _decode_jwt(token, server_secret)

    required = ['tenant_id', 'client_id', 'client_secret', 'workspace_id', 'dataset_id']
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"設定檔 JWT Payload 缺少必要欄位：{', '.join(missing)}")

    return {k: payload[k] for k in required}


# ── Azure AD token ────────────────────────────────────────────────────────────

def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://analysis.windows.net/powerbi/api/.default',
    }).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))['access_token']
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Azure AD 驗證失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")


# ── Power BI API ──────────────────────────────────────────────────────────────

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


# ── CSV conversion ────────────────────────────────────────────────────────────

def result_to_csv(result: dict) -> tuple[str, int]:
    """回傳 (csv_string, row_count)"""
    try:
        table = result['results'][0]['tables'][0]
        rows_data = table.get('rows', [])

        if 'columns' in table:
            columns = [col['name'] for col in table['columns']]
        elif rows_data:
            # EVALUATE ROW() 回應有時不含 columns 陣列，從 rows 的 key 推導
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(
            "用法: python pbi_api_client.py <jwt_config_path> <dax_query_file> [output_csv_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    jwt_path = sys.argv[1]
    dax_file = sys.argv[2]
    if len(sys.argv) > 3:
        csv_path = sys.argv[3]
    else:
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _workspace_root = _find_workspace_root(_script_dir)
        csv_path = os.path.join(_workspace_root, "pbi_query", "query_result.csv")

    try:
        with open(dax_file, 'r', encoding='utf-8') as f:
            dax_query = f.read().strip()
        if not dax_query:
            raise RuntimeError(f"DAX 查詢檔案為空：{dax_file}")

        print("[1/3] 驗證 JWT 設定檔並取出憑證...", file=sys.stderr)
        creds = load_credentials(jwt_path)

        print("[2/3] 向 Azure AD 取得存取權杖...", file=sys.stderr)
        token = get_access_token(creds['tenant_id'], creds['client_id'], creds['client_secret'])

        print("[3/3] 執行 DAX 查詢...", file=sys.stderr)
        result = execute_dax(token, creds['workspace_id'], creds['dataset_id'], dax_query)

        csv_content, row_count = result_to_csv(result)

        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(csv_content)

        print(f"完成，共 {row_count} 筆資料 → {csv_path}", file=sys.stderr)

        # stdout: JSON summary for the skill to parse
        print(json.dumps({"success": True, "row_count": row_count, "csv_path": csv_path}))

    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
