import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


# 此分支三支腳本（bookmarks.py / check_update.py / execute_dax_query.py）實際用到的模組。
REQUIRED_MODULES = [
    'json', 'os', 'sys', 'csv', 'io', 'datetime', 'subprocess',
    'urllib.request', 'urllib.error',
]


def check() -> dict:
    """此 Skill 只依賴標準函式庫，不需安裝任何第三方套件，
    所以這裡不是檢查套件版本，是確認 Python 安裝本身完整（版本、標準函式庫模組皆可用）。

    版本下限 3.9：腳本使用了 PEP 585 的內建泛型註解（例如 `tuple[str, int]`），
    該寫法在 3.9 才於執行期可用。
    """
    version_ok = sys.version_info >= (3, 9)
    version_str = sys.version.split()[0]

    missing_modules = []
    for module_name in REQUIRED_MODULES:
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(module_name)

    return {
        "python_version":  version_str,
        "version_ok":      version_ok,
        "missing_modules": missing_modules,
        "ok":              version_ok and not missing_modules,
    }


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False))
