import json
import os


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


def get_credentials_path(skill_root: str) -> str:
    """azure_ad_credentials.json 存放在 skill_root/config/ 底下。

    此檔案含 Azure AD tenant_id/client_id/client_secret 與各模型的 workspace_id/dataset_id，
    只能由腳本讀取，絕對不可經由 Claude 的 Read 工具開啟或印到 stdout/stderr。
    此 skill 限定在 Claude Code（VS Code 擴充功能或 CLI 終端機）中執行，
    直接操作真實、持續存在的檔案系統，不支援 Claude 桌面版等會話式沙盒環境。
    """
    return os.path.join(skill_root, "config", "azure_ad_credentials.json")


def load_azure_credentials(skill_root: str) -> dict:
    """讀取 azure_ad_credentials.json。僅供 fetch_credential.py/check_setup.py 內部使用，
    回傳值不可被印到 stdout/stderr 或以任何形式交給 Claude。"""
    credentials_path = get_credentials_path(skill_root)
    if not os.path.isfile(credentials_path):
        return {}
    with open(credentials_path, 'r', encoding='utf-8') as f:
        return json.load(f)
