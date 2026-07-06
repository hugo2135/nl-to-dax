import json
import os
import sys
import time
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


def fetch_credential(pbi_config_id: str) -> None:
    mask_key = os.environ.get('PBI_MASK_KEY')
    if not mask_key:
        raise RuntimeError("環境變數 PBI_MASK_KEY 未設定")

    api_url = os.environ.get('CREDENTIAL_SERVER_URL')
    if not api_url:
        raise RuntimeError("環境變數 CREDENTIAL_SERVER_URL 未設定")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = _find_workspace_root(script_dir)
    configs_path = os.path.join(workspace_root, ".claude", "pbi_configs.json")

    print(f"[1/2] 向申請程式取得 Access Token（pbi_config_id={pbi_config_id}）...", file=sys.stderr)

    url = f"{api_url.rstrip('/')}/api/token?pbi_config_id={pbi_config_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {mask_key}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 請求失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")

    access_token = data.get('access_token')
    workspace_id = data.get('workspace_id')
    dataset_id   = data.get('dataset_id')
    expires_in   = data.get('expires_in', 3599)

    missing = [k for k, v in {'access_token': access_token, 'workspace_id': workspace_id, 'dataset_id': dataset_id}.items() if not v]
    if missing:
        raise RuntimeError(f"回傳格式異常，缺少欄位：{missing}；完整回應：{json.dumps(data)}")

    print("[2/2] 寫入 .claude/pbi_configs.json...", file=sys.stderr)

    if os.path.isfile(configs_path):
        with open(configs_path, 'r', encoding='utf-8') as f:
            configs = json.load(f)
    else:
        configs = {}

    configs[pbi_config_id] = {
        "access_token":  access_token,
        "workspace_id":  workspace_id,
        "dataset_id":    dataset_id,
        "expires_at":    int(time.time()) + expires_in,
        "model_version": data.get('model_version'),
    }

    with open(configs_path, 'w', encoding='utf-8') as f:
        json.dump(configs, f, indent=2)

    print(f"完成 → {configs_path}", file=sys.stderr)
    print(json.dumps({"success": True, "path": configs_path}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python fetch_credential.py <pbi_config_id>", file=sys.stderr)
        sys.exit(1)
    try:
        fetch_credential(sys.argv[1])
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
