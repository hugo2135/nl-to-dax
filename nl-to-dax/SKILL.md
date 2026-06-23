Natural Language to DAX Skill (v4)

用途
根據使用者提供的自然語言需求，透過多階段推理，生成適用於 Power BI REST API 的專用 DAX 查詢語法。語意模型由申請程式集中管理，Skill 啟動時自動同步至本地。支援兩種執行模式：只產生 DAX 語法供使用者自行使用，或直接對指定語意模型執行查詢並輸出 CSV 結果。

輸入
執行此 Skill 時，使用者必須明確提供以下兩個輸入：

1. 執行模式（使用者必須明確宣告，Skill 不得自行推斷）：
   - 模式一「只產生 DAX」：完成 Step 0–4，輸出 DAX 查詢語法，不呼叫 Power BI API。
   - 模式二「產生並執行查詢」：完成 Step 0–5，自動呼叫 Power BI REST API 並輸出 CSV。

   若使用者未宣告執行模式，必須先詢問確認，待使用者明確回覆後才能繼續。

2. DAX 需求：以中文或英文描述想查詢的資料內容或計算邏輯。

執行步驟

Step -1：環境檢查與初始化 (Pre-check)

-1.1 偵測作業系統
判斷當前執行環境的作業系統：
- Windows → scripts/windows/trigger_check_setup.ps1
- macOS   → scripts/macos/trigger_check_setup.sh
- Linux   → scripts/linux/trigger_check_setup.sh

-1.2 執行環境檢查腳本
根據作業系統執行對應指令：

Windows（PowerShell）：
powershell -File "scripts\windows\trigger_check_setup.ps1"

macOS（bash）：
bash scripts/macos/trigger_check_setup.sh

Linux（bash）：
bash scripts/linux/trigger_check_setup.sh

腳本回傳 JSON 格式如下：
{"has_mask_key": bool, "has_server_secret": bool, "has_credential": bool, "credential_expired": bool, "model_outdated": bool}

-1.3 依回傳結果分支處理

情況一：has_mask_key = false 或 has_server_secret = false
停止流程，向使用者說明：
「尚未完成初始設定。請前往申請程式完成註冊，取得 PBI_MASK_KEY 後，依下列方式設定三個環境變數：
  Windows:
    $env:PBI_MASK_KEY = "your-key"
    $env:SERVER_JWT_SECRET = "your-secret"
    $env:CREDENTIAL_API_URL = "https://..."
  macOS/Linux:
    export PBI_MASK_KEY="your-key"
    export SERVER_JWT_SECRET="your-secret"
    export CREDENTIAL_API_URL="https://..."
設定完成後重新執行 Skill。」

情況二：has_credential = false 或 credential_expired = true
執行以下指令自動取得憑證：

Windows（PowerShell）：
python "scripts\shared\fetch_credential.py"

macOS / Linux：
python3 scripts/shared/fetch_credential.py

若執行失敗，回報 stderr 錯誤訊息並停止流程。
若執行成功，繼續檢查 model_outdated。

情況三：model_outdated = true
執行以下指令同步語意模型：

Windows（PowerShell）：
python "scripts\shared\fetch_model.py"

macOS / Linux：
python3 scripts/shared/fetch_model.py

若執行失敗，回報 stderr 錯誤訊息並停止流程。

情況四：全部為正常狀態
直接進入 Step 0。

Step 0：載入語意模型 (Load Semantic Model)
本地 pbi_query/ 資料夾存放由申請程式拆分並同步的語意模型 chunks，結構如下：
- pbi_query/relationships.json（全域關聯性，整個語意模型僅一份）
- pbi_query/tables/table_<表名>.json（各資料表結構，每張表一份）

確認以上檔案存在後繼續後續步驟。若 pbi_query/ 不存在或為空，返回 Step -1 強制執行 fetch_model。

Step 0.4：載入並比對篩選設定檔 (Load & Match Filter Profiles)
掃描 filters/ 資料夾，讀取所有 .json 篩選設定檔。每份設定檔的結構如下：

JSON
{
  "filterId": "設定檔唯一識別碼",
  "name": "顯示名稱",
  "description": "說明此篩選的用途",
  "alwaysApply": true/false,
  "overrideDefaults": true/false,
  "contextKeywords": ["關鍵字1", "關鍵字2"],
  "filters": [
    {
      "description": "單一篩選說明",
      "expression": "DAX 篩選表達式",
      "requiredTable": "需要此資料表才套用（可選）"
    }
  ]
}

比對邏輯如下，依序執行：

1. 收集預設篩選：將所有 alwaysApply = true 的設定檔的 filters 合併為「預設篩選集」。

2. 比對情境設定檔：掃描所有 alwaysApply = false 的設定檔，檢查其 contextKeywords 是否出現在使用者的需求文字中。將所有符合的設定檔收集為「命中設定檔清單」。

3. 決定最終篩選集：
   - 若「命中設定檔清單」中有任何設定檔的 overrideDefaults = true，
     則以該設定檔的 filters 完全取代預設篩選集（若命中多個覆蓋設定檔，以最後命中者優先）。
   - 若所有命中的設定檔 overrideDefaults = false（或無任何命中），
     則將命中設定檔的 filters 追加至預設篩選集之後。

4. 最終篩選集將在 Step 4 生成 DAX 時套用。若最終篩選集為空（例如排查模式），則與使用者確認篩選條件。

Step 0 產生的兩類 JSON 格式如下：

表與表關聯的 JSON（relationships.json）：

JSON
{
  "relationships": [
    {
      "fromTable": "Table_Name",
      "fromColumn": "Column_Name",
      "toTable": "Table_Name",
      "toColumn": "Column_Name",
      "cardinality": "ManyToOne",
      "crossFilterDirection": "Single",
      "isActive": true
    }
  ]
}

表與行和量值的 JSON（table_<表名>.json）：

JSON
{
  "table": "Table_Name",
  "description": "Table_Description",
  "columns": [
    {
      "column": "Column_Name",
      "dataType": "DataType",
      "description": "Column_Description"
    }
  ],
  "measures": [
    {
      "measure": "Measure_Name",
      "expression": "DAX_Expression",
      "description": "Measure_Description"
    }
  ]
}

Step 1：識別所需資料表
仔細閱讀使用者的自然語言需求。
當需求中出現模糊詞彙時，必須先中斷流程，向使用者確認猜測，待使用者明確回覆後才能繼續。

根據需求中的語意關鍵字，從已拆分的檔名與結構中，初步盲推/判斷哪些「資料表」是回答該問題的核心主角。

Step 2：驗證表傳遞與關聯
開啟 「表與表關聯的 JSON」。

檢查 Step 1 選出的多張資料表之間，其關聯性是否有效（檢查 isActive 是否為 true、傳遞方向 crossFilterDirection 以及基數 cardinality 是否能支撐篩選邏輯）。

【發問機制】：若發現表之間沒有關聯、關聯斷掉，或使用者需求語意模糊，此時必須中斷流程，先向使用者發問確認，待確認 OK 後才能進入下一步。

Step 3：提取精準欄位與量值
關聯確認無誤後，針對確認需要的資料表，精準開啟對應的 「表與行和量值的 JSON」。

尋找並鎖定計算所需的精確行名稱（Columns）與現有量值（Measures）。若現有量值可複用，優先引用。

Step 4：生成 Power BI REST API 專用 DAX 查詢
根據收集到的欄位與關聯，編寫 DAX 語法。

【技術限制】：此 DAX 是用於 Power BI REST API 端點 POST https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets/{datasetId}/executeQueries 的代碼。

因此，請勿編寫傳統的量值定義（如 [量值名稱] = ...），必須編寫完整的 DAX 查詢語法（必須包含 EVALUATE 關鍵字，並視需求搭配 SUMMARIZECOLUMNS、VAR 變數等查詢專用函數）。

【套用篩選條件】：將 Step 0.4 得出的「最終篩選集」中的篩選條件依下列方式整合進 DAX：

- 使用 SUMMARIZECOLUMNS 時：將每個 filterExpression 作為獨立的篩選引數，透過 FILTER 或直接傳入布林表達式方式加入。
  範例：SUMMARIZECOLUMNS(Table[Column], FILTER(Table, Table[order_type] <> "return_order"), ...)

- 使用 CALCULATETABLE 或 CALCULATE 時：將篩選條件放入計算函數的篩選引數中。

- 套用前需確認 requiredTable 欄位（如有）：若該資料表不在本次查詢範圍內，則跳過該篩選條件。

- 若最終篩選集為空，正常生成 DAX，不加任何篩選條件。

專注於 DAX 代碼本身的正確性與效能。

Step 5：執行 Power BI REST API 查詢
（僅在使用者宣告「模式二：產生並執行查詢」時執行此步驟）

5.1 將 DAX 查詢寫入暫存檔
使用 Write 工具，將 Step 4 產生的完整 DAX 查詢語法（不含程式碼區塊標記）寫入 pbi_query/dax_query.txt。

5.2 執行對應觸發腳本
沿用 Step 0.1 偵測到的作業系統，執行以下對應指令：

Windows（PowerShell）：
powershell -File "scripts\windows\trigger_pbi_api.ps1" -DaxQueryFile "pbi_query\dax_query.txt"

macOS（bash）：
bash scripts/macos/trigger_pbi_api.sh "" "pbi_query/dax_query.txt"

Linux（bash）：
bash scripts/linux/trigger_pbi_api.sh "" "pbi_query/dax_query.txt"

腳本執行成功後，會產生 pbi_query/query_result.csv。
腳本的標準輸出（stdout）會印出一行 JSON 摘要，格式如下：
{"success": true, "row_count": N, "csv_path": "pbi_query/query_result.csv"}

5.3 確認並回報結果
確認 pbi_query/query_result.csv 已成功產生後，向使用者回報：
- 查詢成功，共 N 筆資料
- 結果已輸出至：pbi_query/query_result.csv
- 詢問使用者：「是否需要 Claude 讀取並解讀此 CSV 資料？」

若腳本執行失敗，將 stderr 的錯誤訊息完整回報給使用者後停止。

輸出格式限制
嚴禁輸出任何視覺效果建議、圖表軸說明、或多餘的函數教學。依執行模式輸出如下：

模式一（只產生 DAX）輸出以下兩件事：

1. DAX 查詢
程式碼片段
// Power BI REST API 專用 DAX 查詢
EVALUATE
    // DAX 查詢公式內容

2. 使用到的欄位與量值清單
資料表名稱 1

欄位：Column_Name1, Column_Name2

量值：Measure_Name1

資料表名稱 2

欄位：Column_Name3

模式二（產生並執行查詢）在模式一的基礎上，額外輸出：

3. 執行結果摘要
查詢成功，共 N 筆資料，結果已輸出至 pbi_query/query_result.csv。
是否需要 Claude 讀取並解讀此資料？
