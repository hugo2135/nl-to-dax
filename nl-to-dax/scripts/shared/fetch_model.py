import datetime
import json
import os
import sys
import shutil
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


def fetch_models(workspace_root: str) -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    settings = skill_settings.load_settings(skill_root)

    mask_key = settings.get('PBI_MASK_KEY')
    if not mask_key:
        raise RuntimeError("設定檔缺少 PBI_MASK_KEY，請確認 config/settings.local.json")

    api_url = settings.get('CREDENTIAL_SERVER_URL')
    if not api_url:
        raise RuntimeError("設定檔缺少 CREDENTIAL_SERVER_URL，請確認 config/settings.local.json")

    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)
    pbi_config_dir = os.path.join(workspace_root, "pbi_config")

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

    os.makedirs(pbi_config_dir, exist_ok=True)

    models_index = []
    for model in models:
        pbi_config_id = model.get('pbi_config_id')
        pbi_config_name = model.get('pbi_config_name', '')
        model_version = model.get('model_version')
        model_description = model.get('model_description')
        relationships = model.get('relationships')
        tables = model.get('tables', [])

        if not pbi_config_id or relationships is None:
            print(f"跳過格式異常的模型：{json.dumps(model)[:100]}", file=sys.stderr)
            continue

        model_dir = os.path.join(pbi_config_dir, pbi_config_id)
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
            "pbi_config_id":     pbi_config_id,
            "pbi_config_name":   pbi_config_name,
            "model_version":     model_version,
            "model_description": model_description,
            "table_count":       len(tables),
        })

    # 清除已被管理員收回存取權限的模型快取（不在這次回傳清單中的舊 pbi_config_id 資料夾）
    authorized_ids = {m['pbi_config_id'] for m in models_index}
    for entry in os.listdir(pbi_config_dir):
        entry_path = os.path.join(pbi_config_dir, entry)
        if os.path.isdir(entry_path) and entry not in authorized_ids:
            print(f"移除已收回存取權限的模型快取：{entry}", file=sys.stderr)
            shutil.rmtree(entry_path)

    print("[3/3] 寫入模型索引...", file=sys.stderr)
    with open(os.path.join(pbi_config_dir, "models_index.json"), 'w', encoding='utf-8') as f:
        json.dump(models_index, f, ensure_ascii=False, indent=2)

    with open(os.path.join(pbi_config_dir, "last_sync.json"), 'w', encoding='utf-8') as f:
        json.dump({"last_synced": datetime.date.today().isoformat()}, f, ensure_ascii=False, indent=2)

    print(f"完成，共 {len(models_index)} 個模型", file=sys.stderr)
    print(json.dumps({"success": True, "model_count": len(models_index), "models": models_index}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python fetch_model.py <workspace_root>", file=sys.stderr)
        sys.exit(1)
    try:
        fetch_models(sys.argv[1])
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
