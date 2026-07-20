import datetime
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

REMOTE_URL = "git@github.com:hugo2135/nl-to-dax.git"


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


def _fetch_latest_remote_tag() -> str:
    """借用本機已設定好的 git 憑證查詢遠端 tags，不需要 GitHub API/token。"""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", REMOTE_URL],
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

    latest_version = None
    checked = False
    update_available = False
    try:
        latest_version = _fetch_latest_remote_tag()
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
