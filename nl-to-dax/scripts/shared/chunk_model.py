import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import skill_settings


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>| ]', '_', name)


def parse_model(data: dict) -> tuple[dict, list]:
    """
    接受原始 Power BI F12 匯出 JSON 或簡化語意格式，回傳 (relationships_dict, tables_list)。

    支援的外層結構：
      A. root.updatedModel.clientDataModel.dataModel  （Power BI refresh export）
      B. root.clientDataModel.dataModel               （舊版 export）
      C. root（直接是 dataModel，簡化語意格式）
    """
    if "updatedModel" in data:
        data = data["updatedModel"]

    if "clientDataModel" in data:
        data_model = data["clientDataModel"]["dataModel"]
        fmt = "raw"
    else:
        data_model = data
        fmt = "semantic"

    # ── Relationships ─────────────────────────────────────────
    relationships: list = []
    for rel in data_model.get("relationships", []):
        if fmt == "raw":
            from_table = rel.get("fromTableRef", {}).get("name", "")
            to_table   = rel.get("toTableRef",   {}).get("name", "")
            direction_map = {"OneDirection": "Single", "BothDirections": "Both"}
            chunk = {
                "fromTable":            from_table,
                "fromColumn":           rel.get("fromColumnRef", {}).get("name", ""),
                "toTable":              to_table,
                "toColumn":             rel.get("toColumnRef",   {}).get("name", ""),
                "cardinality":          f"{rel.get('fromCardinality','Many')}To{rel.get('toCardinality','One')}",
                "crossFilterDirection": direction_map.get(rel.get("crossFilteringBehavior", "OneDirection"), "Single"),
                "isActive":             rel.get("isActive", True),
            }
        else:
            from_table = rel.get("fromTable", "")
            to_table   = rel.get("toTable",   "")
            chunk = {
                "fromTable":            from_table,
                "fromColumn":           rel.get("fromColumn", ""),
                "toTable":              to_table,
                "toColumn":             rel.get("toColumn", ""),
                "cardinality":          rel.get("cardinality", ""),
                "crossFilterDirection": rel.get("crossFilterDirection", "Single"),
                "isActive":             rel.get("isActive", True),
            }

        if any(n.startswith(("LocalDateTable_", "DateTableTemplate_")) for n in [from_table, to_table]):
            continue
        relationships.append(chunk)

    # ── Tables ────────────────────────────────────────────────
    tables: list = []
    for table in data_model.get("tables", []):
        name = table.get("name", "")
        if not name:
            print("警告：發現一張缺少 name 欄位的資料表，已跳過", file=sys.stderr)
            continue
        if name.startswith(("LocalDateTable_", "DateTableTemplate_")):
            continue

        entry = {
            "table":       name,
            "description": table.get("description", ""),
            "columns":     [],
            "measures":    [],
        }
        for col in table.get("columns", []):
            if col.get("columnType") == "RowNumber":
                continue
            column_name = col.get("name")
            if not column_name:
                print(f"警告：{name} 有一個欄位缺少 name 欄位，已跳過", file=sys.stderr)
                continue
            entry["columns"].append({
                "column":      column_name,
                "dataType":    col.get("dataType"),
                "description": col.get("description", ""),
            })
        for meas in table.get("measures", []):
            measure_name = meas.get("name")
            if not measure_name:
                print(f"警告：{name} 有一個量值缺少 name 欄位，已跳過", file=sys.stderr)
                continue
            entry["measures"].append({
                "measure":     measure_name,
                "expression":  meas.get("expression", ""),
                "description": meas.get("description", ""),
            })

        if entry["columns"] or entry["measures"]:
            tables.append(entry)
        else:
            print(f"警告：資料表 {name} 沒有可用的欄位或量值，已跳過", file=sys.stderr)

    return {"relationships": relationships}, tables


def _write_model_files(relationships: dict, tables: list, model_dir: str) -> None:
    tables_dir = os.path.join(model_dir, "tables")
    rel_path   = os.path.join(model_dir, "relationships.json")

    if os.path.exists(tables_dir):
        shutil.rmtree(tables_dir)
    os.makedirs(tables_dir)

    with open(rel_path, 'w', encoding='utf-8') as f:
        json.dump(relationships, f, ensure_ascii=False, indent=2)
    print(f"關聯性：{len(relationships['relationships'])} 筆 -> {rel_path}", file=sys.stderr)

    for entry in tables:
        path = os.path.join(tables_dir, f"table_{sanitize_filename(entry['table'])}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
    print(f"資料表：{len(tables)} 張 -> {tables_dir}/", file=sys.stderr)


def chunk_model(workspace_root: str, dataset_id: str,
                 raw_model_json_path: str, description_file_path: str | None) -> dict:
    """dataset_id 直接沿用 Power BI 的 dataset GUID（使用者自行從 azure_ad_credentials.json
    或 Power BI 後台取得，不再另外發明 pbi_config_id 這類代稱）。此腳本完全不讀
    azure_ad_credentials.json，跟憑證/API 無關，只負責把本機 JSON 拆成 nl-to-dax 需要的結構。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = skill_settings.get_skill_root(script_dir)
    workspace_root = skill_settings.validate_workspace_root(workspace_root, skill_root)

    print(f"讀取：{raw_model_json_path}", file=sys.stderr)
    try:
        with open(raw_model_json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"找不到檔案：{raw_model_json_path}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 格式錯誤：{e}")

    _top = raw_data.get("updatedModel", raw_data)
    print(f"格式：{'原始 Power BI' if 'clientDataModel' in _top else '簡化語意模型'}", file=sys.stderr)

    relationships, tables = parse_model(raw_data)
    if not tables:
        raise RuntimeError("解析結果沒有任何可用的資料表，請確認來源 JSON 內容完整（見 SKILL.md 的 F12 擷取步驟）")

    model_dir = os.path.join(workspace_root, "pbi_config", dataset_id)
    os.makedirs(model_dir, exist_ok=True)
    _write_model_files(relationships, tables, model_dir)

    if description_file_path:
        with open(description_file_path, 'r', encoding='utf-8') as f:
            description = f.read().strip()
        with open(os.path.join(model_dir, "description.txt"), 'w', encoding='utf-8') as f:
            f.write(description)
        print(f"模型說明 -> {os.path.join(model_dir, 'description.txt')}", file=sys.stderr)

    return {"success": True, "dataset_id": dataset_id, "table_count": len(tables)}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "用法: python chunk_model.py <workspace_root> <dataset_id> "
            "<raw_model_json_path> [description_file_path]",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        result = chunk_model(
            sys.argv[1], sys.argv[2], sys.argv[3],
            sys.argv[4] if len(sys.argv) > 4 else None,
        )
        print(f"完成，共 {result['table_count']} 張資料表", file=sys.stderr)
        print(json.dumps(result))
    except Exception as e:
        print(f"錯誤：{e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
