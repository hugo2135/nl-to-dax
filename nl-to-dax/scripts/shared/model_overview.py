import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


def build_overview(workspace_root: str, dataset_id: str) -> dict:
    """dataset_name/model_description 已由呼叫端透過 check_setup.py 取得，這裡只負責
    彙整 relationships/tables 本身，不重複讀取或回傳。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)

    model_dir = os.path.join(workspace_root, "pbi_config", dataset_id)
    tables_dir = os.path.join(model_dir, "tables")
    relationships_path = os.path.join(model_dir, "relationships.json")

    if not os.path.isdir(tables_dir) or not os.path.isfile(relationships_path):
        raise RuntimeError(
            f"找不到模型資料：{model_dir}；請先執行 chunk_model.py 產生該 dataset_id 的語意模型。"
        )

    with open(relationships_path, 'r', encoding='utf-8') as f:
        relationships = json.load(f)

    tables = []
    for filename in sorted(os.listdir(tables_dir)):
        if not filename.endswith('.json'):
            continue
        with open(os.path.join(tables_dir, filename), 'r', encoding='utf-8') as f:
            tables.append(json.load(f))

    return {
        "relationships": relationships,
        "tables": tables,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python model_overview.py <workspace_root> <dataset_id>", file=sys.stderr)
        sys.exit(1)
    try:
        overview = build_overview(sys.argv[1], sys.argv[2])
        print(json.dumps(overview, ensure_ascii=False))
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
