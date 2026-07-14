# pbi_config/ 目錄結構說明

此目錄由 `fetch_model.py` 執行時自動產生，內容為使用者當前有權限存取的語意模型快取，
不納入版本控制（見根目錄 `.gitignore`）。以下為實際內容的結構範例。

```
pbi_config/
├── models_index.json          # 所有可用模型的索引
├── last_sync.json             # 上次成功同步的日期，決定每日是否需要重新同步
└── <pbi_config_id>/           # 每個模型一個資料夾，資料夾名稱為 pbi_config_id（UUID）
    ├── relationships.json     # 該模型的全域資料表關聯性
    └── tables/
        └── table_<表名>.json  # 該模型的單一資料表結構（columns、measures）
```

## models_index.json

```json
[
  {
    "pbi_config_id":     "00000000-0000-0000-0000-000000000000",
    "pbi_config_name":   "範例模型顯示名稱",
    "model_version":     1,
    "model_description": "由申請程式管理員撰寫的模型整體說明，可能為 null",
    "table_count":       10
  }
]
```

## last_sync.json

```json
{
  "last_synced": "2026-01-01"
}
```

## \<pbi_config_id\>/relationships.json

```json
{
  "relationships": [
    {
      "fromTable":            "Table_Name",
      "fromColumn":            "Column_Name",
      "toTable":               "Table_Name",
      "toColumn":              "Column_Name",
      "cardinality":           "ManyToOne",
      "crossFilterDirection":  "Single",
      "isActive":              true
    }
  ]
}
```

## \<pbi_config_id\>/tables/table_\<表名\>.json

```json
{
  "table":       "Table_Name",
  "description": "Table_Description",
  "columns": [
    {
      "column":      "Column_Name",
      "dataType":    "DataType",
      "description": "Column_Description"
    }
  ],
  "measures": [
    {
      "measure":     "Measure_Name",
      "expression":  "DAX_Expression",
      "description": "Measure_Description"
    }
  ]
}
```
