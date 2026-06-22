import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def sanitize_filename(name):
    """清理表名，確保轉換成檔名時不會因為特殊字元報錯"""
    return re.sub(r'[\\/*?:"<>| ]', '_', name)

def _find_workspace_root(start_dir: str) -> str:
    """往上找到包含 .claude/ 的目錄，即工作區根目錄。"""
    current = start_dir
    while True:
        if os.path.isdir(os.path.join(current, ".claude")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("找不到工作區根目錄（未找到 .claude 資料夾）")
        current = parent


def process_and_chunk_model(input_json_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = _find_workspace_root(script_dir)

    # 定義輸出的目標資料夾
    output_dir = os.path.join(workspace_root, "pbi_query")
    tables_dir = os.path.join(output_dir, "tables")

    # 清除上一次執行結果，確保不殘留舊資料
    rel_path = os.path.join(output_dir, "relationships.json")
    if os.path.exists(rel_path):
        os.remove(rel_path)
    if os.path.exists(tables_dir):
        shutil.rmtree(tables_dir)

    # 重新建立所需的資料夾結構
    os.makedirs(tables_dir)

    print(f"📂 目標輸出路徑已確認：")
    print(f"   - 關聯性檔案: {output_dir}/relationships.json")
    print(f"   - 資料表資料夾: {tables_dir}/")
    print(f"🔍 正在讀取原始模型檔案: {input_json_path}...")

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到檔案，請確認路徑是否正確：{input_json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤，請確認檔案內容。錯誤訊息: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 讀取原始檔案失敗。錯誤訊息: {e}")
        sys.exit(1)

    # 自動偵測輸入格式
    # 格式 A（原始 Power BI）：clientDataModel.dataModel 包裝，關聯用 fromTableRef/toTableRef
    # 格式 B（簡化語意）：tables/relationships 在根層，欄位已對齊輸出規格
    if "clientDataModel" in raw_data:
        data_model = raw_data["clientDataModel"]["dataModel"]
        fmt = "raw"
    else:
        data_model = raw_data
        fmt = "semantic"

    print(f"📋 偵測到輸入格式：{'原始 Power BI' if fmt == 'raw' else '簡化語意模型'}")

    # ==========================================
    # 1. 處理並輸出「表與表關聯的 JSON」
    # ==========================================
    print("🔗 正在擷取全域關聯性...")
    relationships_output = {"relationships": []}

    for rel in data_model.get("relationships", []):
        if fmt == "raw":
            from_table = rel.get("fromTableRef", {}).get("name", "")
            to_table   = rel.get("toTableRef",   {}).get("name", "")
            raw_card   = f"{rel.get('fromCardinality', 'Many')}To{rel.get('toCardinality', 'One')}"
            direction_map = {"OneDirection": "Single", "BothDirections": "Both"}
            cross = direction_map.get(rel.get("crossFilteringBehavior", "OneDirection"), "Single")
            rel_chunk = {
                "fromTable":           from_table,
                "fromColumn":          rel.get("fromColumnRef", {}).get("name", ""),
                "toTable":             to_table,
                "toColumn":            rel.get("toColumnRef",   {}).get("name", ""),
                "cardinality":         raw_card,
                "crossFilterDirection": cross,
                "isActive":            rel.get("isActive", True),
            }
        else:
            from_table = rel.get("fromTable", "")
            to_table   = rel.get("toTable",   "")
            rel_chunk  = {
                "fromTable":           from_table,
                "fromColumn":          rel.get("fromColumn", ""),
                "toTable":             to_table,
                "toColumn":            rel.get("toColumn", ""),
                "cardinality":         rel.get("cardinality", ""),
                "crossFilterDirection": rel.get("crossFilterDirection", "Single"),
                "isActive":            rel.get("isActive", True),
            }

        # 節省 Token：跳過系統自動生成的內建日期表
        if any(n.startswith(("LocalDateTable_", "DateTableTemplate_")) for n in [from_table, to_table]):
            continue

        relationships_output["relationships"].append(rel_chunk)

    with open(rel_path, 'w', encoding='utf-8') as f:
        json.dump(relationships_output, f, ensure_ascii=False, indent=2)
    print(f"✅ 關聯性處理完成 -> {rel_path}")

    # ==========================================
    # 2. 處理並輸出「各表的行與量值 JSON」
    # ==========================================
    print("📊 正在拆分各資料表與行、量值...")
    table_count = 0

    for table in data_model.get("tables", []):
        table_name = table.get("name", "")

        # 跳過內建隱藏日期表
        if table_name.startswith("LocalDateTable_") or table_name.startswith("DateTableTemplate_"):
            continue

        table_chunk = {
            "table":       table_name,
            "description": table.get("description", ""),
            "columns":     [],
            "measures":    [],
        }

        for col in table.get("columns", []):
            if col.get("columnType") == "RowNumber":
                continue
            table_chunk["columns"].append({
                "column":      col.get("name"),
                "dataType":    col.get("dataType"),
                "description": col.get("description", ""),
            })

        for meas in table.get("measures", []):
            table_chunk["measures"].append({
                "measure":     meas.get("name"),
                "expression":  meas.get("expression", ""),
                "description": meas.get("description", ""),
            })

        if table_chunk["columns"] or table_chunk["measures"]:
            safe_name = sanitize_filename(table_name)
            table_file_path = os.path.join(tables_dir, f"table_{safe_name}.json")
            with open(table_file_path, 'w', encoding='utf-8') as f:
                json.dump(table_chunk, f, ensure_ascii=False, indent=2)
            table_count += 1

    print(f"✅ 所有資料表拆分完成 -> 已儲存 {table_count} 個資料表 JSON 至 {tables_dir}/")
    print(f"🎉 預處理任務執行成功！")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ 使用方式：python chunk_model.py <語意模型JSON檔案路徑>")
        sys.exit(1)
    process_and_chunk_model(sys.argv[1])
