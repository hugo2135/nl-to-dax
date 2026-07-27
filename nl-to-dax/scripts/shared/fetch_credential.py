import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings

# 常見卡關點（供除錯參考，不對外輸出）：
# - Power BI 租戶管理入口需開啟「Allow service principals to use Power BI APIs」，
#   這是 Fabric/Power BI 租戶設定，不是 Azure AD API permissions/consent。
# - Service principal 需被加為目標 workspace 的 Member/Admin。
# - executeQueries 僅支援 Premium/PPU/Fabric 容量的 workspace（走 XMLA endpoint），
#   Pro workspace 會失敗且錯誤訊息不會直接說明原因。
# - Client secret 有效期最長 24 個月，此 skill 不做自動輪替，到期需使用者手動更新
#   azure_ad_credentials.json。


def _get_access_token(tenant_id: str, client_id: str, client_secret: str) -> dict:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    payload = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://analysis.windows.net/powerbi/api/.default",
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            err = json.loads(body)
            raise RuntimeError(f"Azure AD 換取 token 失敗：{err.get('error')} - {err.get('error_description')}")
        except json.JSONDecodeError:
            raise RuntimeError(f"Azure AD 換取 token 失敗 (HTTP {e.code})")


def fetch_credential(workspace_root: str, dataset_id: str) -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    credentials = skill_settings.load_azure_credentials(skill_root)

    model = credentials.get('models', {}).get(dataset_id)
    if not model:
        raise RuntimeError(
            f"azure_ad_credentials.json 的 models 底下找不到 dataset_id={dataset_id}，"
            f"請確認 {skill_settings.get_credentials_path(skill_root)}"
        )

    credential_key = model.get('credential', 'default')
    credential = credentials.get('credentials', {}).get(credential_key)
    if not credential:
        raise RuntimeError(f"azure_ad_credentials.json 的 credentials 底下找不到 {credential_key}")

    missing = [k for k in ('tenant_id', 'client_id', 'client_secret') if not credential.get(k)]
    if missing:
        raise RuntimeError(f"azure_ad_credentials.json 的 credentials.{credential_key} 缺少欄位：{missing}")

    workspace_id = model.get('workspace_id')
    if not workspace_id:
        raise RuntimeError(f"azure_ad_credentials.json 的 models.{dataset_id} 缺少 workspace_id")

    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)
    configs_path = os.path.join(workspace_root, ".claude", "pbi_configs.json")

    print(f"[1/2] 向 Azure AD 換取 Access Token（dataset_id={dataset_id}）...", file=sys.stderr)
    token_data = _get_access_token(credential['tenant_id'], credential['client_id'], credential['client_secret'])

    access_token = token_data.get('access_token')
    expires_in   = token_data.get('expires_in', 3599)
    if not access_token:
        raise RuntimeError("Azure AD 回應格式異常，缺少 access_token")

    print("[2/2] 寫入 .claude/pbi_configs.json...", file=sys.stderr)

    if os.path.isfile(configs_path):
        with open(configs_path, 'r', encoding='utf-8') as f:
            configs = json.load(f)
    else:
        configs = {}

    configs[dataset_id] = {
        "access_token": access_token,
        "workspace_id": workspace_id,
        "dataset_id":   dataset_id,
        "expires_at":   int(time.time()) + expires_in,
    }

    os.makedirs(os.path.dirname(configs_path), exist_ok=True)
    with open(configs_path, 'w', encoding='utf-8') as f:
        json.dump(configs, f, indent=2)

    print(f"完成 → {configs_path}", file=sys.stderr)
    print(json.dumps({"success": True, "path": configs_path}))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python fetch_credential.py <workspace_root> <dataset_id>", file=sys.stderr)
        sys.exit(1)
    try:
        fetch_credential(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
