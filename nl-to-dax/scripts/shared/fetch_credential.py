import json
import os
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def _find_skill_root(start_dir: str) -> str:
    current = start_dir
    while True:
        if os.path.isfile(os.path.join(current, "SKILL.md")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("找不到 Skill 根目錄（未找到 SKILL.md）")
        current = parent


def fetch_credential() -> None:
    mask_key = os.environ.get('PBI_MASK_KEY')
    if not mask_key:
        raise RuntimeError("環境變數 PBI_MASK_KEY 未設定")

    api_url = os.environ.get('CREDENTIAL_SERVER_URL')
    if not api_url:
        raise RuntimeError("環境變數 CREDENTIAL_SERVER_URL 未設定")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = _find_skill_root(script_dir)
    output_path = os.path.join(skill_root, "config", "pbi_credentials.jwt")

    print("[1/2] 向申請程式取得憑證...", file=sys.stderr)

    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/credential",
        headers={"Authorization": f"Bearer {mask_key}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 請求失敗 (HTTP {e.code}): {e.read().decode('utf-8')}")

    jwt_token = data.get('jwt')
    if not jwt_token:
        raise RuntimeError(f"回傳格式異常，缺少 jwt 欄位：{json.dumps(data)}")

    print("[2/2] 寫入憑證檔案...", file=sys.stderr)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(jwt_token)

    print(f"完成 → {output_path}", file=sys.stderr)
    print(json.dumps({"success": True, "path": output_path}))


if __name__ == "__main__":
    try:
        fetch_credential()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
