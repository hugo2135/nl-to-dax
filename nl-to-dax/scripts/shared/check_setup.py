import json
import os
import sys

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


_SETTINGS_TEMPLATE = {
    "env": {
        "PBI_MASK_KEY": "",
        "CREDENTIAL_SERVER_URL": "http://localhost:5173/"
    }
}


def _ensure_settings_local(workspace_root: str) -> bool:
    """若 settings.local.json 不存在則自動建立，回傳是否新建。"""
    settings_path = os.path.join(workspace_root, ".claude", "settings.local.json")
    if os.path.isfile(settings_path):
        return False
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(_SETTINGS_TEMPLATE, f, indent=2, ensure_ascii=False)
    print(f"已建立 {settings_path}", file=sys.stderr)
    return True


def check() -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = _find_workspace_root(script_dir)
    pbi_query_dir = os.path.join(workspace_root, "pbi_query")

    settings_created = _ensure_settings_local(workspace_root)

    has_mask_key = bool(os.environ.get('PBI_MASK_KEY'))
    has_server_url = bool(os.environ.get('CREDENTIAL_SERVER_URL'))
    has_model = os.path.isfile(os.path.join(pbi_query_dir, "models_index.json"))

    return {
        "settings_created": settings_created,
        "has_mask_key":     has_mask_key,
        "has_server_url":   has_server_url,
        "has_model":        has_model,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
