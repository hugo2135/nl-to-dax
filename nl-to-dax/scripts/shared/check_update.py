import datetime
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def load_update_source(skill_root: str) -> dict:
    """讀取 config/update_source.json（來源倉庫設定）。

    刻意不寫死倉庫網址：同一份 skill 可能部署自 GitHub、自架 Gitea 或內部鏡像，
    網址屬於部署資訊而非程式邏輯。檔案不存在時回傳空 dict，呼叫端據此靜默略過
    版本檢查——沒設定來源不該讓主流程失敗。

    `repo_url` 走本機既有的 git 憑證（SSH key 或 credential manager），
    SSH／HTTPS 皆可，git 會自行判斷，腳本不需要區分。
    """
    path = os.path.join(skill_root, "config", "update_source.json")
    if not os.path.isfile(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _parse_version(version_str: str):
    """把 'v0.2' / '0.2' 這類版號字串轉成 (major, build) tuple 以利比較，格式不符則回傳 None。"""
    if not version_str:
        return None
    parts = version_str.strip().lstrip('v').split('.')
    if len(parts) != 2:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _read_current_version(skill_root: str) -> str:
    version_path = os.path.join(skill_root, "VERSION")
    if not os.path.isfile(version_path):
        return None
    with open(version_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def _fetch_latest_remote_tag(repo_url: str) -> str:
    """借用本機已設定好的 git 憑證查詢遠端 tags，不需要 GitHub API/token。"""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", repo_url],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-remote 執行失敗")

    versions = []
    for line in result.stdout.splitlines():
        if "refs/tags/" not in line:
            continue
        tag = line.split("refs/tags/", 1)[1]
        if tag.endswith("^{}"):
            tag = tag[:-3]
        parsed = _parse_version(tag)
        if parsed:
            versions.append((parsed, tag))

    if not versions:
        return None

    versions.sort(key=lambda item: item[0])
    return versions[-1][1]


def check_update(skill_root: str) -> dict:
    """每天最多向遠端查詢一次最新版號；查詢失敗一律靜默略過，不影響主流程。"""
    state_path = os.path.join(skill_root, "config", "update_check.json")
    today = datetime.date.today().isoformat()

    state = {}
    if os.path.isfile(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)

    current_version = _read_current_version(skill_root)

    if state.get('last_checked') == today:
        return {
            "current_version":   current_version,
            "latest_version":    state.get('latest_version'),
            "update_available":  state.get('update_available', False),
            "checked":           state.get('checked', False),
        }

    repo_url = load_update_source(skill_root).get('repo_url')
    if not repo_url:
        # 沒設定來源倉庫：靜默略過，不寫入狀態檔（之後設定好就會立刻生效）
        return {
            "current_version":  current_version,
            "latest_version":   None,
            "update_available": False,
            "checked":          False,
        }

    latest_version = None
    checked = False
    update_available = False
    try:
        latest_version = _fetch_latest_remote_tag(repo_url)
        checked = latest_version is not None
        if checked and current_version:
            latest_parsed = _parse_version(latest_version)
            current_parsed = _parse_version(current_version)
            if latest_parsed and current_parsed:
                update_available = latest_parsed > current_parsed
    except Exception as e:
        print(f"版本檢查失敗（略過，不影響主流程）：{e}", file=sys.stderr)

    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump({
            "last_checked":      today,
            "latest_version":    latest_version,
            "update_available":  update_available,
            "checked":           checked,
        }, f, indent=2, ensure_ascii=False)

    return {
        "current_version":   current_version,
        "latest_version":    latest_version,
        "update_available":  update_available,
        "checked":           checked,
    }


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.dirname(os.path.dirname(script_dir))
    print(json.dumps(check_update(skill_root), ensure_ascii=False))
