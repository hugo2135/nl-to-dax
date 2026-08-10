#!/usr/bin/env python3
"""
Power BI REST API 客戶端

用法: python pbi_api_client.py <pbi_config_id> <dax_query_file> [output_csv_path]

stdout: JSON 摘要  {"success": true, "row_count": N, "csv_path": "..."}
stderr: 執行進度與錯誤訊息
"""

import sys
import json
import os
import time
import csv
import io
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


# ── Token ─────────────────────────────────────────────────────────────────────

def load_token(pbi_config_id: str) -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    configs_path = skill_settings.get_token_cache_path(skill_root)

    if not os.path.isfile(configs_path):
        raise RuntimeError(
            f"找不到 {configs_path}\n"
            "請先執行 fetch_credential.py 取得 Access Token。"
        )

    with open(configs_path, 'r', encoding='utf-8') as f:
        configs = json.load(f)

    data = configs.get(pbi_config_id)
    if not data:
        raise RuntimeError(
            f"pbi_configs.json 中找不到 pbi_config_id={pbi_config_id}\n"
            "請先執行 fetch_credential.py 取得 Access Token。"
        )

    expires_at = data.get('expires_at', 0)
    if expires_at and expires_at < time.time():
        exp_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(expires_at))
        print(f"警告：Access Token 已於 {exp_str} 過期，請重新執行 fetch_credential.py", file=sys.stderr)

    required = ['access_token', 'workspace_id', 'dataset_id']
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"pbi_configs.json 缺少必要欄位：{', '.join(missing)}")

    return data


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
    if len(sys.argv) < 4:
        print(
            "用法: python pbi_api_client.py <workspace_root> <pbi_config_id> <dax_query_file> [output_csv_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    workspace_root = sys.argv[1]
    pbi_config_id = sys.argv[2]
    dax_file = sys.argv[3]
    if len(sys.argv) > 4:
        csv_path = sys.argv[4]
    else:
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _skill_root = skill_settings.get_skill_root(_script_dir)
        _workspace_root = skill_settings.validate_workspace_root(workspace_root, _skill_root)
        csv_path = os.path.join(_workspace_root, "pbi_query", "query_result.csv")

    try:
        with open(dax_file, 'r', encoding='utf-8') as f:
            dax_query = f.read().strip()
        if not dax_query:
            raise RuntimeError(f"DAX 查詢檔案為空：{dax_file}")

        print("[1/2] 載入 Access Token...", file=sys.stderr)
        token_data = load_token(pbi_config_id)

        print("[2/2] 執行 DAX 查詢...", file=sys.stderr)
        result = execute_dax(
            token_data['access_token'],
            token_data['workspace_id'],
            token_data['dataset_id'],
            dax_query,
        )

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
