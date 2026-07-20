import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


def check(workspace_root: str) -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)
    pbi_config_dir = os.path.join(workspace_root, "pbi_config")

    settings_created = skill_settings.ensure_settings_local(skill_root)
    settings = skill_settings.load_settings(skill_root)

    has_mask_key = bool(settings.get('PBI_MASK_KEY'))
    has_server_url = bool(settings.get('CREDENTIAL_SERVER_URL'))
    has_model = os.path.isfile(os.path.join(pbi_config_dir, "models_index.json"))

    # settings.local.json 的路徑資訊在此一併算好給呼叫端（Claude）直接使用，
    # 不要讓 Claude 自己判斷/計算相對路徑——那是純推理，容易算錯或生出不存在的路徑。
    settings_path = skill_settings.get_settings_path(skill_root)
    settings_path_relative = None
    try:
        common = os.path.commonpath([os.path.normcase(settings_path), os.path.normcase(workspace_root)])
        if os.path.normcase(common) == os.path.normcase(workspace_root):
            settings_path_relative = os.path.relpath(settings_path, workspace_root).replace(os.sep, '/')
    except ValueError:
        pass  # Windows 上不同磁碟機時 commonpath 會丟例外，視為不在 workspace 底下

    # 管理員可能隨時變動使用者的「已分配語意模型」，has_model 只代表本地曾經同步過，
    # 不代表清單仍是最新的，因此每日至少強制重新同步一次，避免永遠沿用舊的模型清單。
    last_sync_path = os.path.join(pbi_config_dir, "last_sync.json")
    last_synced = None
    if os.path.isfile(last_sync_path):
        with open(last_sync_path, 'r', encoding='utf-8') as f:
            last_synced = json.load(f).get('last_synced')
    model_sync_stale = last_synced != datetime.date.today().isoformat()

    return {
        "settings_created":       settings_created,
        "has_mask_key":           has_mask_key,
        "has_server_url":         has_server_url,
        "has_model":              has_model,
        "model_sync_stale":       model_sync_stale,
        "settings_path_absolute": settings_path,
        "settings_path_relative": settings_path_relative,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_setup.py <workspace_root>", file=sys.stderr)
        sys.exit(1)
    try:
        print(json.dumps(check(sys.argv[1])))
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
