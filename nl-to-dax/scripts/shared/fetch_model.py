import json
import os
import sys
import shutil
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def _find_workspace_root(start_dir: str) -> str:
    current = start_dir
    while True:
        if os.path.isdir(os.path.join(current, ".claude")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("找不到工作區根目錄（未找到 .claude 資料夾）")
        current = parent


def fetch_model() -> None:
    mask_key = os.environ.get('PBI_MASK_KEY')
    if not mask_key:
        raise RuntimeError("環境變數 PBI_MASK_KEY 未設定")

    api_url = os.environ.get('CREDENTIAL_API_URL')
    if not api_url:
        raise RuntimeError("環境變數 CREDENTIAL_API_URL 未設定")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = _find_workspace_root(script_dir)
    pbi_query_dir = os.path.join(workspace_root, "pbi_query")
    tables_dir = os.path.join(pbi_query_dir, "tables")

    print("[1/3] 向申請程式取得語意模型...", file=sys.stderr)

    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/model",
        headers={"Authorization": f"Bearer {mask_key}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 請求失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")

    model_version = data.get('model_version')
    relationships = data.get('relationships')
    tables = data.get('tables', [])

    if relationships is None:
        raise RuntimeError(f"回傳格式異常，缺少 relationships 欄位：{json.dumps(data)}")

    print("[2/3] 清除舊資料並寫入新 chunks...", file=sys.stderr)

    if os.path.exists(tables_dir):
        shutil.rmtree(tables_dir)
    os.makedirs(tables_dir)

    rel_path = os.path.join(pbi_query_dir, "relationships.json")
    with open(rel_path, 'w', encoding='utf-8') as f:
        json.dump(relationships, f, ensure_ascii=False, indent=2)

    for table in tables:
        table_name = table.get('table', 'unknown')
        safe_name = table_name.replace(' ', '_')
        table_path = os.path.join(tables_dir, f"table_{safe_name}.json")
        with open(table_path, 'w', encoding='utf-8') as f:
            json.dump(table, f, ensure_ascii=False, indent=2)

    print("[3/3] 寫入版本記錄...", file=sys.stderr)
    version_path = os.path.join(pbi_query_dir, "model_version.json")
    with open(version_path, 'w', encoding='utf-8') as f:
        json.dump({"model_version": model_version}, f)

    print(f"完成，model_version={model_version}，共 {len(tables)} 張資料表", file=sys.stderr)
    print(json.dumps({"success": True, "model_version": model_version, "table_count": len(tables)}))


if __name__ == "__main__":
    try:
        fetch_model()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
