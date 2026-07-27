import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


def _has_credentials_file(credentials: dict) -> bool:
    for cred in credentials.get('credentials', {}).values():
        if cred.get('tenant_id') and cred.get('client_id') and cred.get('client_secret'):
            return True
    return False


def _has_structure(model_dir: str) -> bool:
    return (
        os.path.isfile(os.path.join(model_dir, "relationships.json"))
        and os.path.isdir(os.path.join(model_dir, "tables"))
    )


def check(workspace_root: str) -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)
    pbi_config_dir = os.path.join(workspace_root, "pbi_config")

    credentials = skill_settings.load_azure_credentials(skill_root)
    has_credentials_file = _has_credentials_file(credentials)
    registered_models = credentials.get('models', {})

    models = []
    for dataset_id, model in registered_models.items():
        model_dir = os.path.join(pbi_config_dir, dataset_id)
        has_structure = _has_structure(model_dir)

        table_count = None
        model_description = None
        if has_structure:
            tables_dir = os.path.join(model_dir, "tables")
            table_count = len([f for f in os.listdir(tables_dir) if f.endswith('.json')])
            description_path = os.path.join(model_dir, "description.txt")
            if os.path.isfile(description_path):
                with open(description_path, 'r', encoding='utf-8') as f:
                    model_description = f.read().strip()

        models.append({
            "dataset_id":        dataset_id,
            "dataset_name":      model.get('dataset_name'),
            "has_structure":     has_structure,
            "table_count":       table_count,
            "model_description": model_description,
        })

    orphaned_structures = []
    if os.path.isdir(pbi_config_dir):
        for entry in os.listdir(pbi_config_dir):
            entry_path = os.path.join(pbi_config_dir, entry)
            if os.path.isdir(entry_path) and entry not in registered_models and _has_structure(entry_path):
                orphaned_structures.append(entry)

    return {
        "has_credentials_file": has_credentials_file,
        "models":                models,
        "orphaned_structures":   orphaned_structures,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_setup.py <workspace_root>", file=sys.stderr)
        sys.exit(1)
    try:
        print(json.dumps(check(sys.argv[1]), ensure_ascii=False))
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
