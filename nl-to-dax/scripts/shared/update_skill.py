"""
把本機 Skill 更新到遠端倉庫的指定版本。

用法: python update_skill.py [目標版本，例如 v1.1；省略則用遠端最新的 tag]

來源倉庫讀自 `config/update_source.json`（見 `update_source.json.example`）。

## 為什麼不是 git pull

部署方式是「把 nl-to-dax/ 目錄複製進 skill 路徑」，安裝結果通常不是 git working
tree，`git pull` 沒有東西可以拉。因此改為淺層 clone 指定 tag 到暫存目錄，再把
程式碼檔案覆蓋過去。

## 保護規則（重要）

`config/` 底下同時放著程式碼範本與使用者資料。更新**只覆蓋程式碼**，
以下檔案一律原封不動——它們是使用者的設定與資料，不屬於倉庫內容：

    site_domain.json / update_source.json / bookmarks.json
    env_probe.json   / update_check.json  / 任何非 .example 的 .json

## 失敗安全

先把即將被覆蓋的檔案備份到暫存目錄，任一步失敗就整批還原，
不會讓 skill 停在「更新到一半」的壞掉狀態。

stdout: JSON 摘要；stderr: 進度與錯誤訊息
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import check_update

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 這些檔名（或副檔名組合）屬於使用者資料，更新時絕不覆蓋、絕不刪除。
PROTECTED_CONFIG_FILES = {
    "site_domain.json",
    "update_source.json",
    "bookmarks.json",
    "env_probe.json",
    "update_check.json",
    "azure_ad_credentials.json",
    "settings.local.json",
    "pbi_configs.json",
}

# 會被更新覆蓋的頂層項目（其餘一律不碰）
UPDATABLE_ENTRIES = ["SKILL.md", "VERSION", "scripts", "filters"]


def _is_protected(rel_path: str) -> bool:
    """config/ 底下非 .example 的 .json 一律視為使用者資料。"""
    parts = rel_path.replace('\\', '/').split('/')
    if parts[0] != "config":
        return False
    name = parts[-1]
    if name in PROTECTED_CONFIG_FILES:
        return True
    return name.endswith('.json') and not name.endswith('.example')


def clone_version(repo_url: str, ref: str, dest: str) -> None:
    print(f"取得 {ref} ...", file=sys.stderr)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, repo_url, dest],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"無法取得版本 {ref}：{result.stderr.strip() or 'git clone 失敗'}"
        )


def _collect_updates(source_skill_dir: str) -> list:
    """列出要覆蓋的檔案（相對於 skill root），已排除受保護的使用者資料。"""
    updates = []
    for entry in UPDATABLE_ENTRIES:
        src = os.path.join(source_skill_dir, entry)
        if not os.path.exists(src):
            continue
        if os.path.isfile(src):
            updates.append(entry)
            continue
        for root, _dirs, files in os.walk(src):
            for name in files:
                if name.endswith('.pyc'):
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, source_skill_dir).replace('\\', '/')
                updates.append(rel)

    # config/ 只更新 .example 範本
    src_config = os.path.join(source_skill_dir, "config")
    if os.path.isdir(src_config):
        for name in sorted(os.listdir(src_config)):
            rel = f"config/{name}"
            if os.path.isfile(os.path.join(src_config, name)) and not _is_protected(rel):
                updates.append(rel)

    return updates


def _collect_removals(updates: list) -> list:
    """列出本機有、但新版已經沒有的程式碼檔案。

    `scripts/`／`filters/` 完全來自倉庫、不含使用者資料，因此做成完整鏡像：
    上游刪掉的檔案本機也要刪掉。否則歷次改版的殘骸會一直累積——例如舊版的
    check_python_env.py、skill_settings.py、fetch_model.py 在更新後仍留著，
    造成新舊模組混在同一個目錄的狀態。

    `config/` 不在此列：那裡有使用者資料，只增不刪。
    """
    keep = set(updates)
    removals = []
    for entry in ("scripts", "filters"):
        base = os.path.join(SKILL_ROOT, entry)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, SKILL_ROOT).replace('\\', '/')
                if name.endswith('.pyc') or '__pycache__' in rel:
                    removals.append(rel)      # 順手清掉編譯快取，避免載到舊模組
                elif rel not in keep:
                    removals.append(rel)
    return removals


def apply_update(source_skill_dir: str, updates: list, removals: list, backup_dir: str) -> None:
    """先備份再覆蓋／刪除；任一步失敗即整批還原。"""
    applied = []
    removed = []
    try:
        for rel in updates:
            dst = os.path.join(SKILL_ROOT, rel)
            if os.path.isfile(dst):
                bak = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(bak), exist_ok=True)
                shutil.copy2(dst, bak)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(source_skill_dir, rel), dst)
            applied.append(rel)

        for rel in removals:
            dst = os.path.join(SKILL_ROOT, rel)
            if not os.path.isfile(dst):
                continue
            bak = os.path.join(backup_dir, rel)
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(dst, bak)
            os.remove(dst)
            removed.append(rel)
    except Exception:
        print("更新失敗，正在還原...", file=sys.stderr)
        for rel in applied + removed:
            bak = os.path.join(backup_dir, rel)
            if os.path.isfile(bak):
                dst = os.path.join(SKILL_ROOT, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(bak, dst)
        raise


def locate_skill_dir(clone_dir: str, subdir) -> str:
    """找出 clone 下來的倉庫裡，哪一層對應部署後的 SKILL_ROOT（也就是 SKILL.md 所在層）。

    倉庫可能是兩種佈局：
      A. 巢狀——倉庫根目錄還有 README/CLAUDE.md 等，skill 放在某個子目錄底下
      B. 扁平——倉庫本身就是 skill，根目錄直接是 SKILL.md/scripts/

    `skill_subdirectory` 沒設定時自動判斷（先看根目錄，再看常見的子目錄名），
    設定了就完全照設定值——包含刻意填空字串代表「就是根目錄」。
    自動判斷是為了避免佈局 B 的使用者因為漏填而拿到看不懂的錯誤。
    """
    if subdir is not None:
        candidate = os.path.join(clone_dir, subdir) if subdir else clone_dir
        if not os.path.isfile(os.path.join(candidate, "SKILL.md")):
            location = f"{subdir}/" if subdir else "根目錄"
            raise RuntimeError(
                f"來源倉庫的{location}底下找不到 SKILL.md，"
                "請確認 update_source.json 的 skill_subdirectory 設定正確"
                "（倉庫本身就是 skill 時請填空字串 \"\"）"
            )
        return candidate

    if os.path.isfile(os.path.join(clone_dir, "SKILL.md")):
        return clone_dir
    for name in sorted(os.listdir(clone_dir)):
        path = os.path.join(clone_dir, name)
        if name != ".git" and os.path.isdir(path) and os.path.isfile(os.path.join(path, "SKILL.md")):
            print(f"自動偵測到 skill 位於倉庫的 {name}/ 底下", file=sys.stderr)
            return path
    raise RuntimeError(
        "來源倉庫中找不到 SKILL.md（根目錄與第一層子目錄都沒有）。"
        "請確認 repo_url 指向正確的倉庫，或用 skill_subdirectory 明確指定位置"
    )


def _prune_empty_dirs() -> None:
    """清掉 scripts/ 底下更新後變空的目錄（例如舊版的 windows/macos/linux、__pycache__）。

    只刪真的空的目錄，所以不會弄丟任何東西。在檔案都處理完、確定不會再回滾之後才執行。
    """
    base = os.path.join(SKILL_ROOT, "scripts")
    if not os.path.isdir(base):
        return
    for root, dirs, _files in os.walk(base, topdown=False):
        for name in dirs:
            path = os.path.join(root, name)
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except OSError:
                pass


def main() -> None:
    source = check_update.load_update_source(SKILL_ROOT)
    repo_url = source.get('repo_url')
    if not repo_url:
        raise RuntimeError(
            "尚未設定更新來源。請複製 config/update_source.json.example 為 "
            "config/update_source.json 並填入 repo_url"
        )
    subdir = source.get('skill_subdirectory')

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        target = check_update._fetch_latest_remote_tag(repo_url)
        if not target:
            raise RuntimeError("遠端倉庫沒有任何符合版號格式的 tag，無法判斷要更新到哪一版")

    before = check_update._read_current_version(SKILL_ROOT)

    with tempfile.TemporaryDirectory(prefix="nl-to-dax-update-") as tmp:
        clone_dir = os.path.join(tmp, "repo")
        backup_dir = os.path.join(tmp, "backup")
        clone_version(repo_url, target, clone_dir)

        source_skill_dir = locate_skill_dir(clone_dir, subdir)

        updates = _collect_updates(source_skill_dir)
        if not updates:
            raise RuntimeError("來源倉庫沒有可更新的檔案，請確認倉庫內容是否正確")
        removals = _collect_removals(updates)

        print(f"更新 {len(updates)} 個檔案，移除 {len(removals)} 個舊檔...", file=sys.stderr)
        apply_update(source_skill_dir, updates, removals, backup_dir)

    _prune_empty_dirs()
    after = check_update._read_current_version(SKILL_ROOT)

    # 版本已變，強制下次重新檢查，不要讓今天的舊快取蓋掉結果
    state_path = os.path.join(SKILL_ROOT, "config", "update_check.json")
    if os.path.isfile(state_path):
        os.remove(state_path)

    print(f"完成：{before} → {after}", file=sys.stderr)
    print(json.dumps({
        "success": True,
        "version_before": before,
        "version_after": after,
        "target": target,
        "files_updated": len(updates),
        "files_removed": len(removals),
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
