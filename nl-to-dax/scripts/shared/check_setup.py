import json
import os
import sys
import base64
import time

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


def _find_workspace_root(start_dir: str) -> str:
    current = start_dir
    while True:
        if os.path.isdir(os.path.join(current, ".claude")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("找不到工作區根目錄（未找到 .claude 資料夾）")
        current = parent


def _get_jwt_exp(jwt_path: str) -> int | None:
    try:
        with open(jwt_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
        return payload.get('exp')
    except Exception:
        return None


def _get_jwt_model_version(jwt_path: str) -> int | None:
    try:
        with open(jwt_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
        return payload.get('model_version')
    except Exception:
        return None


def _get_local_model_version(pbi_query_dir: str) -> int | None:
    version_file = os.path.join(pbi_query_dir, "model_version.json")
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return json.load(f).get('model_version')
    except Exception:
        return None


def check() -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = _find_skill_root(script_dir)
    workspace_root = _find_workspace_root(script_dir)

    credential_path = os.path.join(skill_root, "config", "pbi_credentials.jwt")
    pbi_query_dir = os.path.join(workspace_root, "pbi_query")

    has_mask_key = bool(os.environ.get('PBI_MASK_KEY'))
    has_server_secret = bool(os.environ.get('SERVER_JWT_SECRET'))
    has_credential = os.path.isfile(credential_path)

    credential_expired = False
    model_outdated = False

    if has_credential:
        exp = _get_jwt_exp(credential_path)
        if exp is None or exp < time.time():
            credential_expired = True

        jwt_version = _get_jwt_model_version(credential_path)
        local_version = _get_local_model_version(pbi_query_dir)
        if jwt_version is not None and jwt_version != local_version:
            model_outdated = True

    return {
        "has_mask_key":      has_mask_key,
        "has_server_secret": has_server_secret,
        "has_credential":    has_credential,
        "credential_expired": credential_expired,
        "model_outdated":    model_outdated,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
