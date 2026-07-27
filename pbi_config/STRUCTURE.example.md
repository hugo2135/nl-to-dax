# pbi_config/ 目錄結構說明

此目錄由 `chunk_model.py` 執行時自動產生，內容為使用者自行透過瀏覽器 F12 擷取並轉換的語意模型快取，
不納入版本控制（見根目錄 `.gitignore`）。以下為實際內容的結構範例。

```
pbi_config/
└── <dataset_id>/              # 每個模型一個資料夾，資料夾名稱為該模型的 Power BI dataset_id
    ├── relationships.json     # 該模型的全域資料表關聯性
    ├── description.txt        # 選填：模型整體說明（chunk_model.py 的 description_file 參數提供）
    └── tables/
        └── table_<表名>.json  # 該模型的單一資料表結構（columns、measures）
```

模型的顯示名稱（`dataset_name`）與 `workspace_id` 不存放在這裡，而是登記在
`<SKILL_ROOT>/config/azure_ad_credentials.json` 的 `models.<dataset_id>` 底下；
`check_setup.py` 會交叉比對這裡的資料夾與該檔案的登記狀態，回傳每個模型是否已就緒可查詢。

## \<dataset_id\>/relationships.json

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

## \<dataset_id\>/tables/table_\<表名\>.json

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
