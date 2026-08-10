"""啟動前置檢查：一次回傳 Skill 決定 Step -1 走向所需的全部狀態。

用法：
  python preflight.py <workspace_root>

取代先前分開呼叫的 check_python_env.py / check_setup.py / check_update.py /
bookmarks.py list——四次 subprocess 併為一次，SKILL.md 也只需描述一組指令。
各腳本仍可獨立執行，本檔只是薄薄的編排層，不複製任何邏輯。

**版本閘門必須在其餘 import 之前**：這個檔案負責回報「Python 版本夠不夠」，
若在頂層就 import check_setup/bookmarks 等模組，而那些模組用到較新語法或
在舊版 Python 載入失敗，使用者拿到的會是一串 traceback，而不是乾淨的
「請升級 Python」訊息。因此其餘 import 一律延後到閘門之後。

stdout: 單一 JSON；stderr: 人類可讀訊息。
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Python < 3.7 沒有 reconfigure；版本檢查會在下面照常回報

MIN_VERSION = (3, 9)

# 此分支各腳本實際 import 的標準函式庫模組。
REQUIRED_MODULES = [
    'json', 'os', 'sys', 'shutil', 'csv', 'io', 'time',
    'datetime', 'subprocess', 'urllib.request', 'urllib.error',
]


def check_python() -> dict:
    """只依賴 json/sys，確保在任何 Python 3.x 上都能執行並回報結果。"""
    missing = []
    for name in REQUIRED_MODULES:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)

    version_ok = sys.version_info >= MIN_VERSION
    return {
        "python_version":  sys.version.split()[0],
        "version_ok":      version_ok,
        "missing_modules": missing,
        "ok":              version_ok and not missing,
    }


def _safe(section: str, fn):
    """單一區段失敗不應拖垮整包——回報該區段的錯誤，其餘照常回傳。"""
    try:
        return fn()
    except Exception as e:
        print(f"[{section}] 檢查失敗（不影響其他區段）：{e}", file=sys.stderr)
        return {"ok": False, "error": str(e)}


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python preflight.py <workspace_root>", file=sys.stderr)
        sys.exit(1)
    workspace_root = sys.argv[1]

    python_report = check_python()
    if not python_report["ok"]:
        # 閘門未通過：立即回報並結束，不 import 任何其他模組。
        print(json.dumps({"python": python_report, "gated": True}, ensure_ascii=False))
        return

    # 通過閘門後才 import，理由見檔案開頭說明。
    import check_setup
    import check_update
    import bookmarks
    import skill_settings

    skill_root = skill_settings.get_skill_root(os.path.dirname(os.path.abspath(__file__)))

    result = {
        "python":    python_report,
        "gated":     False,
        "setup":     _safe("setup",     lambda: check_setup.check(workspace_root)),
        "update":    _safe("update",    lambda: check_update.check_update(skill_root)),
        "bookmarks": _safe("bookmarks", lambda: bookmarks.cmd_list()),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
