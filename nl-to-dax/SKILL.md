---
name: nl-to-dax
description: 根據使用者以中文或英文描述的自然語言需求，透過多階段推理生成適用於 Power BI REST API 的專用 DAX 查詢語法，直接以 Azure AD 服務主體換取 Access Token 後呼叫 Power BI REST API 執行查詢並輸出 CSV 結果。當使用者想要查詢 Power BI 語意模型中的資料、要求產生 DAX 查詢、或提到「查訂單」「查銷量」等業務資料查詢需求時，使用此 skill。
---

# Natural Language to DAX Skill（solo 分支）

用途
根據使用者提供的自然語言需求，透過多階段推理，生成適用於 Power BI REST API 的專用 DAX 查詢語法，並自動呼叫 Power BI REST API 執行查詢、輸出 CSV 結果。此分支為自用模式：Azure AD 憑證直接設定在本機（不經過任何中央 Server），語意模型結構由使用者自行透過瀏覽器 F12 擷取後用 `chunk_model.py` 轉換取得。

輸入
執行此 Skill 時，使用者需提供：

DAX 需求：以中文或英文描述想查詢的資料內容或計算邏輯。

執行步驟

Step -1：環境檢查與初始化 (Pre-check)

-1.0 定位根目錄
此 SKILL.md 所在的目錄即為 Skill 根目錄，以下稱 <SKILL_ROOT>。
<WORKSPACE_ROOT> 為使用者當前操作的專案／工作區目錄，與 <SKILL_ROOT> 的實際安裝位置無關——
skill 可能安裝在專案內的 `.claude/skills/`，也可能安裝在使用者層級的 `~/.claude/skills/`，
兩種情況下 <WORKSPACE_ROOT> 都是使用者目前工作的專案目錄，不可用 <SKILL_ROOT> 往上推算。
所有腳本與檔案路徑皆使用絕對路徑。執行任何指令前，必須先確認兩個根目錄的實際路徑，
並將 <WORKSPACE_ROOT> 明確作為參數傳給以下所有腳本（腳本本身不會猜測工作區根目錄，
若傳入的路徑不存在會直接回報錯誤及 Skill 目前所在路徑）。

-1.1 偵測作業系統
判斷當前執行環境的作業系統：
- Windows → <SKILL_ROOT>\scripts\windows\trigger_check_setup.ps1
- macOS   → <SKILL_ROOT>/scripts/macos/trigger_check_setup.sh
- Linux   → <SKILL_ROOT>/scripts/linux/trigger_check_setup.sh

-1.1b 檢查 Python 環境
在執行任何 Skill 腳本前，先確認 Python 可用、版本 ≥ 3.9、且所有腳本會用到的標準函式庫模組都能正常匯入（此 Skill 只依賴標準函式庫，不需安裝任何第三方套件，所以這裡不是檢查套件，是檢查 Python 安裝本身是否完整）。依 -1.1 偵測到的作業系統執行對應指令：

Windows（PowerShell）：
powershell -File "<SKILL_ROOT>\scripts\windows\trigger_check_python_env.ps1"

macOS（bash）：
bash "<SKILL_ROOT>/scripts/macos/trigger_check_python_env.sh"

Linux（bash）：
bash "<SKILL_ROOT>/scripts/linux/trigger_check_python_env.sh"

若指令本身找不到（例如「'python' 不是內部或外部命令」／「command not found」，代表連 Python 都沒裝，腳本無法執行）：告知使用者「找不到 Python，請先安裝 Python 3.9 以上版本」，停止流程。

若指令有執行，回傳 JSON 格式如下：
{"python_version": "3.x.x", "version_ok": bool, "missing_modules": [...], "ok": bool}

- `ok = true`：檢查通過，繼續下一步。
- `version_ok = false`：告知使用者目前偵測到的版本（`python_version`），請其升級至 3.9 以上，停止流程。
- `missing_modules` 非空（極少見，通常代表 Python 安裝不完整或為精簡版）：告知使用者缺少哪些標準函式庫模組，建議重新安裝完整版 Python，停止流程。

-1.2 執行環境檢查腳本
根據作業系統執行對應指令（將 <SKILL_ROOT>、<WORKSPACE_ROOT> 替換為實際路徑）：

Windows（PowerShell）：
powershell -File "<SKILL_ROOT>\scripts\windows\trigger_check_setup.ps1" -WorkspaceRoot "<WORKSPACE_ROOT>"

macOS（bash）：
bash "<SKILL_ROOT>/scripts/macos/trigger_check_setup.sh" "<WORKSPACE_ROOT>"

Linux（bash）：
bash "<SKILL_ROOT>/scripts/linux/trigger_check_setup.sh" "<WORKSPACE_ROOT>"

腳本回傳 JSON 格式如下：
{"has_credentials_file": bool, "models": [{"dataset_id", "dataset_name", "has_structure": bool, "table_count", "model_description"}], "orphaned_structures": ["dataset_id", ...]}

**安全規則（絕對遵守）**：`<SKILL_ROOT>/config/azure_ad_credentials.json` 含 Azure AD `tenant_id`/`client_id`/`client_secret`。**絕對不要用 Read 工具開啟這個檔案，絕對不要用 Edit 工具寫入這個檔案，絕對不要在對話中詢問或接受這些值**。這些值只能由使用者自行在編輯器/檔案總管中填寫，Claude 全程不經手。即使使用者主動在對話中貼出憑證，也只回覆「已收到但不會使用此值」，並提醒對方因為這組憑證已經進入對話紀錄，應立即到 Azure AD 撤銷/重新產生該 client secret。`dataset_id`/`workspace_id` 不是機密資訊，可以正常顯示給使用者。

-1.3 依回傳結果分支處理

若 has_credentials_file = false：
向使用者說明（依 README「憑證設定」章節）：

「在開始使用前，您需要先完成 Azure AD 憑證設定：

1. 複製 `<SKILL_ROOT>/config/azure_ad_credentials.json.example` 為同目錄下的 `azure_ad_credentials.json`
2. 自行在編輯器中填入您的 Azure AD 服務主體 `tenant_id`/`client_id`/`client_secret`，並在 `models` 底下為每個要查詢的資料集新增一筆（以 `dataset_id` 為 key，填入 `dataset_name`/`workspace_id`）

完成後重新執行 /nl-to-dax。」
流程到此停止。

若 has_credentials_file = true 但 models 為空陣列：
提醒使用者尚未在 `azure_ad_credentials.json` 的 `models` 底下登記任何資料集（`dataset_id`/`dataset_name`/`workspace_id`），依 README「憑證設定」章節完成後重新執行。流程到此停止。

若 models 中沒有任何一筆 has_structure = true：
列出 `models` 中每一筆的 `{dataset_name}（{dataset_id}）`，告知使用者這些資料集都還沒有語意模型結構，請選擇其中一個要處理的資料集，並依 README「取得語意模型結構」章節，用瀏覽器 F12 開發者工具從 BI 系統的 Network 分頁複製模型結構回應存成 JSON，執行：

Windows（PowerShell）：
python "<SKILL_ROOT>\scripts\shared\chunk_model.py" "<WORKSPACE_ROOT>" <dataset_id> "<json 檔路徑>" ["<說明檔路徑>"]

macOS / Linux：
python3 "<SKILL_ROOT>/scripts/shared/chunk_model.py" "<WORKSPACE_ROOT>" <dataset_id> "<json 檔路徑>" ["<說明檔路徑>"]

`<dataset_id>` 必須是使用者選擇的那筆 `models` 項目的 key。若 `orphaned_structures` 非空，一併提醒使用者：這些 `dataset_id` 底下有語意模型結構、但已經不在 `azure_ad_credentials.json` 的 `models` 裡登記，可能是已移除或打錯 key，建議確認。
流程到此停止。

-1.4 檢查 Skill 版本
執行以下指令（內部每日最多實際查詢一次，其餘時間直接讀快取，不會有感延遲）：

Windows（PowerShell）：
python "<SKILL_ROOT>\scripts\shared\check_update.py"

macOS / Linux：
python3 "<SKILL_ROOT>/scripts/shared/check_update.py"

回傳 JSON 格式：{"current_version": "0.1", "latest_version": "0.2"|null, "update_available": bool, "checked": bool}
此步驟純粹是提醒性質，不影響主流程：
- 若執行失敗、或 checked = false（例如沒有網路、沒有 git 權限、遠端尚未打過任何 tag）：靜默略過，不告知使用者。
- 若 update_available = true：在稍後的回覆中簡短提醒一次即可，例如「（偵測到新版本 v{latest_version}，目前使用 v{current_version}，建議之後更新部署）」，不要中斷流程、不要因此停下來等使用者回應。

不論以上步驟是否執行，接著都進行模型選擇（見下方「模型選擇流程」）。

模型選擇流程：
1. 使用 -1.2 已取得的 `models` 中 `has_structure = true` 的項目（不需要再另外讀取任何檔案，check_setup.py 已經算好可查詢的模型清單）
2. 若只有一個 → 自動選定，告知使用者：「使用模型：{dataset_name}」
3. 若有多個 → 列出 `{dataset_name}（{dataset_id}）` 供使用者選擇，等待使用者指定後繼續
4. 記住選定的 dataset_id，後續步驟皆使用此 ID
5. 依選定的 dataset_id 呼叫以下指令向 Azure AD 換取該模型的 Access Token：

Windows（PowerShell）：
python "<SKILL_ROOT>\scripts\shared\fetch_credential.py" "<WORKSPACE_ROOT>" <dataset_id>

macOS / Linux：
python3 "<SKILL_ROOT>/scripts/shared/fetch_credential.py" "<WORKSPACE_ROOT>" <dataset_id>

若執行失敗：向使用者說明「Access Token 取得失敗，請確認 azure_ad_credentials.json 的憑證與 workspace_id 是否正確」，並停止流程。
不要在回覆中逐字貼出 stderr 的原始錯誤內容——其中可能包含 Azure AD App ID 等基礎設施細節，不適合暴露給一般使用者；僅在使用者主動要求查看技術細節時才提供。
若執行成功，執行「模型概覽展示流程」（見下方），再詢問使用者：「您想查詢什麼？」

模型概覽展示流程：
1. 檢查「模型選擇流程」步驟 1 取得的 `models` 中，該模型的 model_description 欄位是否有值（使用者可透過 `chunk_model.py` 的 description_file 參數預先寫入整體說明）。

若 model_description 有值（優先路徑，節省 token）：
直接以 model_description 作為模型概覽輸出，不需執行 model_overview.py、不需讀取 relationships/tables、不需自行分群或彙整量值——這份說明已涵蓋這些內容。輸出格式：

---
以下是 **{dataset_name}** 模型中可查詢的主要資料範圍：

{model_description}
---

若 model_description 為 null（回退路徑）：
執行以下指令取得該模型的整合結構化資料（relationships + 所有 tables），不要自行用 Read 工具逐一開啟 tables/ 目錄下的檔案，也不要委派給其他 Skill 或 subagent 處理：

Windows（PowerShell）：
powershell -File "<SKILL_ROOT>\scripts\windows\trigger_model_overview.ps1" -WorkspaceRoot "<WORKSPACE_ROOT>" -PbiConfigId "<dataset_id>"

macOS / Linux：
bash "<SKILL_ROOT>/scripts/macos/trigger_model_overview.sh" "<WORKSPACE_ROOT>" "<dataset_id>"（Linux 對應 scripts/linux 路徑；`-PbiConfigId`/位置參數傳入的值即為 dataset_id，腳本本身不需要修改）

若執行失敗，回報 stderr 錯誤訊息並停止流程。

直接使用上一步 stdout 回傳的 JSON（不需再讀取其他檔案，也不需另外委派任何 Skill 產生說明文件）中的 relationships、tables（與 Step 0 的 relationships.json／table_<表名>.json 內容相同），接著：
- 彙整每張資料表的 table 名稱、description、columns、measures 欄位
- 依資料表名稱與描述，以語意判斷將資料表分群（例如：訂單/銷售、客戶/會員、產品、庫存、經銷商等，依實際模型靈活命名）
- 彙整所有資料表中的 measures，列出名稱清單（不需列出 DAX 表達式）
- 以下列格式輸出模型概覽：

---
以下是 **{dataset_name}** 模型中可查詢的主要資料範圍：

**可查詢的資料主題**

{主題一}
| 資料表 | 說明 |
|--------|------|
| 表名   | 描述 |

{主題二}
...

**預建 KPI 量值（量值區）**
已有現成量值可直接使用，例如：
- {量值群組一}：{量值1}、{量值2}、...
- {量值群組二}：...
---

Step 0：載入語意模型 (Load Semantic Model)
本地 pbi_config/<dataset_id>/ 資料夾存放由 `chunk_model.py` 拆分產生的語意模型 chunks，結構如下：
- pbi_config/<dataset_id>/relationships.json（全域關聯性，整個語意模型僅一份）
- pbi_config/<dataset_id>/tables/table_<表名>.json（各資料表結構，每張表一份）

此時應已於 -1.3 確認存在（該模型在 `models` 中的 `has_structure = true`）。若意外不存在（例如檔案被手動清除），請使用者依「取得語意模型結構」章節重新執行 `chunk_model.py`。

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

5.1 將 DAX 查詢寫入暫存檔
使用 Write 工具，將 Step 4 產生的完整 DAX 查詢語法（不含程式碼區塊標記）寫入 <WORKSPACE_ROOT>/pbi_query/dax_query.txt（使用絕對路徑）。

5.2 執行對應觸發腳本
沿用 Step -1.1 偵測到的作業系統及 Step -1.3 模型選擇流程中記住的 <dataset_id>，執行以下對應指令（`-PbiConfigId`/位置參數傳入的值即為 dataset_id）：

Windows（PowerShell）：
powershell -File "<SKILL_ROOT>\scripts\windows\trigger_pbi_api.ps1" -WorkspaceRoot "<WORKSPACE_ROOT>" -PbiConfigId "<dataset_id>" -DaxQueryFile "<WORKSPACE_ROOT>\pbi_query\dax_query.txt"

macOS（bash）：
bash "<SKILL_ROOT>/scripts/macos/trigger_pbi_api.sh" "<WORKSPACE_ROOT>" "<dataset_id>" "<WORKSPACE_ROOT>/pbi_query/dax_query.txt"

Linux（bash）：
bash "<SKILL_ROOT>/scripts/linux/trigger_pbi_api.sh" "<WORKSPACE_ROOT>" "<dataset_id>" "<WORKSPACE_ROOT>/pbi_query/dax_query.txt"

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
嚴禁輸出任何視覺效果建議、圖表軸說明、或多餘的函數教學。輸出以下內容：

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

3. 執行結果摘要
查詢成功，共 N 筆資料，結果已輸出至 pbi_query/query_result.csv。
是否需要 Claude 讀取並解讀此資料？
