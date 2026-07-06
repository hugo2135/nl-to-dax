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


def fetch_models() -> None:
    mask_key = os.environ.get('PBI_MASK_KEY')
    if not mask_key:
        raise RuntimeError("環境變數 PBI_MASK_KEY 未設定")

    api_url = os.environ.get('CREDENTIAL_SERVER_URL')
    if not api_url:
        raise RuntimeError("環境變數 CREDENTIAL_SERVER_URL 未設定")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = _find_workspace_root(script_dir)
    pbi_query_dir = os.path.join(workspace_root, "pbi_query")

    print("[1/3] 向申請程式取得語意模型清單...", file=sys.stderr)

    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/models",
        headers={"Authorization": f"Bearer {mask_key}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 請求失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")

    models = data.get('models', [])
    if not models:
        raise RuntimeError(f"回傳格式異常，缺少 models 欄位或清單為空：{json.dumps(data)}")

    print(f"[2/3] 寫入 {len(models)} 個模型的資料...", file=sys.stderr)

    os.makedirs(pbi_query_dir, exist_ok=True)

    models_index = []
    for model in models:
        pbi_config_id = model.get('pbi_config_id')
        pbi_config_name = model.get('pbi_config_name', '')
        model_version = model.get('model_version')
        relationships = model.get('relationships')
        tables = model.get('tables', [])

        if not pbi_config_id or relationships is None:
            print(f"跳過格式異常的模型：{json.dumps(model)[:100]}", file=sys.stderr)
            continue

        model_dir = os.path.join(pbi_query_dir, pbi_config_id)
        tables_dir = os.path.join(model_dir, "tables")

        if os.path.exists(tables_dir):
            shutil.rmtree(tables_dir)
        os.makedirs(tables_dir)

        with open(os.path.join(model_dir, "relationships.json"), 'w', encoding='utf-8') as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

        for table in tables:
            table_name = table.get('table', 'unknown')
            safe_name = table_name.replace(' ', '_')
            with open(os.path.join(tables_dir, f"table_{safe_name}.json"), 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2)

        models_index.append({
            "pbi_config_id":   pbi_config_id,
            "pbi_config_name": pbi_config_name,
            "model_version":   model_version,
            "table_count":     len(tables),
        })

    print("[3/3] 寫入模型索引...", file=sys.stderr)
    with open(os.path.join(pbi_query_dir, "models_index.json"), 'w', encoding='utf-8') as f:
        json.dump(models_index, f, ensure_ascii=False, indent=2)

    print(f"完成，共 {len(models_index)} 個模型", file=sys.stderr)
    print(json.dumps({"success": True, "model_count": len(models_index), "models": models_index}))


if __name__ == "__main__":
    try:
        fetch_models()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
