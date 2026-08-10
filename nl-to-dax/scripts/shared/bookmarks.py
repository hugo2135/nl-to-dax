"""查詢書籤：把驗證過的 DAX 查詢連同原始需求存起來，之後可直接重跑或重新生成。

用法：
  python bookmarks.py list [model_key]
  python bookmarks.py show <model_key> <name>
  python bookmarks.py save <model_key> <name> <dax_file> [request_text]
  python bookmarks.py delete <model_key> <name>

stdout: JSON 摘要（供 Skill 解析）；stderr: 人類可讀的進度與錯誤訊息。

DAX 一律從檔案讀入、由本腳本負責 JSON 轉義——DAX 內含大量雙引號
（例如 order_type IN {"a","b"}），交給 LLM 手寫進 JSON 極易出錯。

刻意不依賴 skill_settings，讓此檔案能原封不動 port 到三條分支
（mcp-oauth 分支沒有 skill_settings.py）。
"""

import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOKMARKS_PATH = os.path.join(SKILL_ROOT, "config", "bookmarks.json")
PROBE_PATH = os.path.join(SKILL_ROOT, "config", "env_probe.json")


def detect_persistence() -> dict:
    """判斷本機檔案能不能跨對話存活。

    兩層判斷：
      1. 正面證明——探針檔存在且記錄的日期早於今天，代表檔案確實跨天存活過。
      2. 首次執行時的推測——沙盒環境的 skill 掛載在 /mnt/skills/ 底下，
         Claude Code CLI/VS Code 則是使用者家目錄或專案內的實際路徑。

    第 2 層失準時（例如掛載路徑日後改變），第 1 層會在下次執行自動修正判斷。
    """
    today = datetime.date.today().isoformat()
    first_seen = None
    if os.path.isfile(PROBE_PATH):
        try:
            with open(PROBE_PATH, 'r', encoding='utf-8') as f:
                first_seen = json.load(f).get('first_seen')
        except (json.JSONDecodeError, OSError):
            first_seen = None

    if first_seen and first_seen < today:
        return {"persistent": True, "proven": True}

    if first_seen is None:
        os.makedirs(os.path.dirname(PROBE_PATH), exist_ok=True)
        with open(PROBE_PATH, 'w', encoding='utf-8') as f:
            json.dump({"first_seen": today}, f, ensure_ascii=False, indent=2)

    normalized = SKILL_ROOT.replace('\\', '/')
    looks_ephemeral = normalized.startswith('/mnt/skills/')
    return {"persistent": not looks_ephemeral, "proven": False}


def _load() -> dict:
    if not os.path.isfile(BOOKMARKS_PATH):
        return {}
    with open(BOOKMARKS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save(data: dict) -> None:
    """暫存檔 + os.replace 原子寫入，避免寫到一半中斷造成檔案損毀。"""
    os.makedirs(os.path.dirname(BOOKMARKS_PATH), exist_ok=True)
    tmp_path = BOOKMARKS_PATH + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, BOOKMARKS_PATH)


def _listing(entries: dict) -> list:
    listing = [
        {
            "name":       name,
            "request":    entry.get('request'),
            "created_at": entry.get('created_at'),
            "updated_at": entry.get('updated_at'),
        }
        for name, entry in entries.items()
    ]
    listing.sort(key=lambda item: item.get('updated_at') or '', reverse=True)
    return listing


def cmd_list(model_key: str = None) -> dict:
    """只回傳名稱與需求摘要，不含 DAX 內容——每次對話開頭都會呼叫，不應灌爆上下文。

    不指定 model_key 時回傳所有模型的分組清單，供 preflight 一次帶回，
    這樣選定模型後就不需要再呼叫一次。
    """
    data = _load()
    env = detect_persistence()

    if model_key is not None:
        return {"success": True, "model_key": model_key, "bookmarks": _listing(data.get(model_key, {})), **env}

    return {
        "success": True,
        "models": {key: _listing(entries) for key, entries in data.items()},
        **env,
    }


def cmd_show(model_key: str, name: str) -> dict:
    entry = _load().get(model_key, {}).get(name)
    if not entry:
        raise RuntimeError(f"找不到書籤：{name}（模型 {model_key}）")
    return {"success": True, "model_key": model_key, "name": name, **entry}


def cmd_save(model_key: str, name: str, dax_file: str, request_text: str = None) -> dict:
    try:
        with open(dax_file, 'r', encoding='utf-8') as f:
            dax = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"找不到 DAX 檔案：{dax_file}")
    if not dax:
        raise RuntimeError(f"DAX 檔案為空：{dax_file}")

    data = _load()
    entries = data.setdefault(model_key, {})
    today = datetime.date.today().isoformat()
    existing = entries.get(name)

    entries[name] = {
        "request":    request_text if request_text is not None else (existing or {}).get('request'),
        "dax":        dax,
        "created_at": (existing or {}).get('created_at', today),
        "updated_at": today,
    }
    _save(data)

    env = detect_persistence()
    print(f"已儲存書籤「{name}」→ {BOOKMARKS_PATH}", file=sys.stderr)
    return {
        "success": True,
        "model_key": model_key,
        "name": name,
        "overwritten": existing is not None,
        **env,
    }


def cmd_delete(model_key: str, name: str) -> dict:
    data = _load()
    entries = data.get(model_key, {})
    if name not in entries:
        raise RuntimeError(f"找不到書籤：{name}（模型 {model_key}）")
    del entries[name]
    if not entries:
        del data[model_key]
    _save(data)
    print(f"已刪除書籤「{name}」", file=sys.stderr)
    return {"success": True, "model_key": model_key, "name": name}


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "list":
        result = cmd_list(args[0] if args else None)
    elif command == "show":
        if len(args) < 2:
            raise RuntimeError("用法: bookmarks.py show <model_key> <name>")
        result = cmd_show(args[0], args[1])
    elif command == "save":
        if len(args) < 3:
            raise RuntimeError("用法: bookmarks.py save <model_key> <name> <dax_file> [request_text]")
        result = cmd_save(args[0], args[1], args[2], args[3] if len(args) > 3 else None)
    elif command == "delete":
        if len(args) < 2:
            raise RuntimeError("用法: bookmarks.py delete <model_key> <name>")
        result = cmd_delete(args[0], args[1])
    else:
        raise RuntimeError(f"未知的指令：{command}")

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
