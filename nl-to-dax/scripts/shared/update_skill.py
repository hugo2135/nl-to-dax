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


def apply_update(source_skill_dir: str, updates: list, backup_dir: str) -> None:
    """先備份再覆蓋；任一步失敗即整批還原。"""
    applied = []
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
    except Exception:
        print("更新失敗，正在還原...", file=sys.stderr)
        for rel in applied:
            bak = os.path.join(backup_dir, rel)
            if os.path.isfile(bak):
                shutil.copy2(bak, os.path.join(SKILL_ROOT, rel))
        raise


def main() -> None:
    source = check_update.load_update_source(SKILL_ROOT)
    repo_url = source.get('repo_url')
    if not repo_url:
        raise RuntimeError(
            "尚未設定更新來源。請複製 config/update_source.json.example 為 "
            "config/update_source.json 並填入 repo_url"
        )
    subdir = source.get('skill_subdirectory', 'nl-to-dax')

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

        source_skill_dir = os.path.join(clone_dir, subdir) if subdir else clone_dir
        if not os.path.isfile(os.path.join(source_skill_dir, "SKILL.md")):
            raise RuntimeError(
                f"來源倉庫的 {subdir}/ 底下找不到 SKILL.md，"
                "請確認 update_source.json 的 skill_subdirectory 設定正確"
            )

        updates = _collect_updates(source_skill_dir)
        if not updates:
            raise RuntimeError("來源倉庫沒有可更新的檔案，請確認倉庫內容是否正確")

        print(f"更新 {len(updates)} 個檔案...", file=sys.stderr)
        apply_update(source_skill_dir, updates, backup_dir)

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
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
