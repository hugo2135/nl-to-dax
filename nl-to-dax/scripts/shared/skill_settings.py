import json
import os
import sys


def get_skill_root(script_dir: str) -> str:
    return os.path.dirname(os.path.dirname(script_dir))


def validate_workspace_root(workspace_root: str, skill_root: str) -> str:
    """驗證呼叫端傳入的工作區根目錄。

    工作區根目錄一律由呼叫端（SKILL.md 驅動的流程）明確傳入，不在此處用路徑猜測，
    這樣無論 skill 安裝在專案的 .claude/skills/ 或使用者層級的 ~/.claude/skills/，
    都不影響工作區根目錄的判斷。
    """
    if not os.path.isdir(workspace_root):
        raise RuntimeError(
            f"工作區根目錄不存在：{workspace_root}；Skill 目前位於：{skill_root}；"
            f"無法定位 pbi_query 資料夾。"
        )
    return workspace_root


def _read_default_credential_server_url(skill_root: str) -> str:
    """讀取 config/default_credential_server_url.txt 作為 CREDENTIAL_SERVER_URL 的預設值。

    此檔案與 skill_settings.py 分離，方便不同部署（例如公開原始碼倉庫 vs. 內部倉庫）
    各自維護不同的預設網址，不需要修改程式碼。檔案不存在時預設為空字串，
    使用者需自行於 settings.local.json 填入。
    """
    path = os.path.join(skill_root, "config", "default_credential_server_url.txt")
    if not os.path.isfile(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def get_settings_path(skill_root: str) -> str:
    """settings.local.json 存放在 skill_root/config/ 底下。

    此 skill 限定在 Claude Code（VS Code 擴充功能或 CLI 終端機）中執行，
    直接操作真實、持續存在的檔案系統，不支援 Claude 桌面版等會話式沙盒環境。
    """
    return os.path.join(skill_root, "config", "settings.local.json")


def get_token_cache_path(skill_root: str) -> str:
    """Access Token 快取（pbi_configs.json）放在 skill_root/config/ 底下。

    刻意不放在使用者的工作區（<WORKSPACE_ROOT>/.claude/）：那是使用者當下開啟的任意
    程式碼專案，該專案的 .gitignore 是否排除 .claude/ 不在本 skill 掌控範圍內，
    含 access token 的檔案有被誤 commit 的風險。放在 skill 自己的 config/ 底下，
    使用者層級安裝時完全不在任何專案 repo 內，專案內安裝時也受本 repo 的 .gitignore 保護。
    """
    return os.path.join(skill_root, "config", "pbi_configs.json")


def ensure_settings_local(skill_root: str) -> bool:
    """若 config/settings.local.json 不存在則自動建立，回傳是否新建。"""
    settings_path = get_settings_path(skill_root)
    if os.path.isfile(settings_path):
        return False
    template = {
        "PBI_MASK_KEY": "",
        "CREDENTIAL_SERVER_URL": _read_default_credential_server_url(skill_root),
    }
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f"已建立 {settings_path}", file=sys.stderr)
    return True


def load_settings(skill_root: str) -> dict:
    settings_path = get_settings_path(skill_root)
    if not os.path.isfile(settings_path):
        return {}
    with open(settings_path, 'r', encoding='utf-8') as f:
        return json.load(f)
