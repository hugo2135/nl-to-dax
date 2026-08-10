---
name: nl-to-dax
description: 根據使用者以中文或英文描述的自然語言需求，透過多階段推理生成適用於 Power BI REST API 的專用 DAX 查詢語法，自動呼叫 Power BI REST API 執行查詢並輸出 CSV 結果。當使用者想要查詢 Power BI 語意模型中的資料、要求產生 DAX 查詢、或提到「查訂單」「查銷量」等業務資料查詢需求時，使用此 skill。
---

# Natural Language to DAX Skill

用途
根據使用者提供的自然語言需求，透過多階段推理，生成適用於 Power BI REST API 的專用 DAX 查詢語法，並自動呼叫 Power BI REST API 執行查詢、輸出 CSV 結果。語意模型由申請程式集中管理，Skill 啟動時自動同步至本地。

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

**執行腳本的方式**：一律直接呼叫 Python，不要透過任何 shell wrapper——Windows 用 `python`，
macOS / Linux 用 `python3`，除了這個指令名稱之外其餘參數完全相同，因此以下各步驟只寫一種形式。
路徑分隔符號用 `/` 即可，Windows 的 Python 同樣接受。
（先前版本曾提供 .ps1/.sh 觸發腳本，已移除：Windows 預設的 PowerShell ExecutionPolicy 是
Restricted，會直接擋掉未簽署的 .ps1，反而製造一個直接呼叫 Python 不會有的失敗點。）

-1.1 執行前置檢查（單一指令取得所有狀態）
Python 環境、設定狀態、版本更新、查詢書籤四項檢查已整併為一支腳本，只需執行一次：

python "<SKILL_ROOT>/scripts/shared/preflight.py" "<WORKSPACE_ROOT>"

若指令本身找不到（例如「'python' 不是內部或外部命令」／「command not found」，代表連 Python 都沒裝）：告知使用者「找不到 Python，請先安裝 Python 3.9 以上版本」，停止流程。

回傳單一 JSON：
{
  "python":    {"python_version": "3.x.x", "version_ok": bool, "missing_modules": [...], "ok": bool},
  "gated":     bool,
  "setup":     {"settings_created": bool, "has_mask_key": bool, "has_server_url": bool, "has_model": bool, "model_sync_stale": bool, "settings_path_absolute": "...", "settings_path_relative": "..."|null},
  "update":    {"current_version": "0.1", "latest_version": "0.2"|null, "update_available": bool, "checked": bool},
  "bookmarks": {"models": {"<pbi_config_id>": [{"name", "request", "created_at", "updated_at"}]}, "persistent": bool, "proven": bool}
}

先看 `python` 與 `gated`：
- `gated = true` 代表 Python 版本或標準函式庫不符，此時只有 `python` 欄位有值，其餘欄位不存在。
  - `version_ok = false`：告知使用者目前偵測到的版本（`python_version`），請其升級至 3.9 以上，停止流程。
  - `missing_modules` 非空（極少見，通常代表 Python 安裝不完整或為精簡版）：告知使用者缺少哪些標準函式庫模組，建議重新安裝完整版 Python，停止流程。
- `gated = false` → 繼續往下依 `setup` 分支處理。

各區段互相獨立：某一段檢查失敗時該欄位會是 `{"ok": false, "error": "..."}`，其餘欄位仍然有效。`update`/`bookmarks` 失敗不影響主流程，靜默略過即可；`setup` 失敗才需要回報使用者。

-1.2 依 setup 結果分支處理

若 has_mask_key = false：
先用 Read 工具讀取上一步 JSON 回傳的 `settings_path_absolute`（settings.local.json 的實際路徑，位於使用者家目錄下，不是 <SKILL_ROOT>/config/ 底下——skill 執行環境每次對話可能重新產生，設定檔必須放在持續存在的位置），取得實際的 CREDENTIAL_SERVER_URL 值。
向使用者說明（若 settings_created = true，開頭加一句「已自動建立設定檔。」；不要輸出未解析的 {CREDENTIAL_SERVER_URL} 佔位符）：
服務網址本身就是合法 URL，直接用 `[實際網址](實際網址)` 呈現即可。
settings.local.json 的連結**直接使用上一步 JSON 回傳的欄位，不要自己判斷或計算路徑**（自行推算容易算錯、甚至生出不存在的路徑）：
- 若 `settings_path_relative` 不是 null：直接照抄這個值呈現為 Markdown 連結，例如 `[settings.local.json](settings_path_relative 的值)`。
- 若 `settings_path_relative` 是 null：改為純文字顯示 `settings_path_absolute` 的值，不做成連結。
「在開始使用前，您需要完成以下申請流程取得個人金鑰（PBI_MASK_KEY）：

1. 開啟服務網址：[實際網址](實際網址)
2. 點選「立即註冊」，填入 Email 與密碼後申請帳號
3. 等待管理員開通帳號（開通後才能登入）
4. 登入後進入個人頁面，點選「領取 PBI_MASK_KEY」
5. 金鑰只顯示一次，請立即複製並妥善保存

取得金鑰後，您可以直接將金鑰提供給我，我幫您填入設定檔；或自行開啟 settings.local.json（依上述規則呈現為相對路徑連結或純文字絕對路徑）填入 PBI_MASK_KEY 欄位。」
等待使用者回應後：
- 若使用者提供金鑰 → 使用 Edit 工具將金鑰寫入 settings.local.json 的 PBI_MASK_KEY 欄位，完成後告知使用者重新執行 /nl-to-dax
- 若使用者選擇自行設定 → 告知其設定完成後重新執行 /nl-to-dax
流程到此停止。

若 has_mask_key = true：
若 has_model = false 或 model_sync_stale = true，先執行以下指令同步最新語意模型（管理員可能隨時變動使用者的已分配模型，has_model = true 只代表本地曾經同步過、不代表清單仍最新，因此每日至少強制重新同步一次）：

python "<SKILL_ROOT>/scripts/shared/fetch_model.py" "<WORKSPACE_ROOT>"

若執行失敗，回報 stderr 錯誤訊息並停止流程（即使本地已有舊的模型快取，也不要靜默沿用，因為無法確認使用者目前是否仍有權限存取這些模型）。

-1.3 版本更新提醒
使用 -1.1 已取得的 `update` 欄位，純粹是提醒性質，不影響主流程：
- 若 `checked = false` 或該區段回傳 `{"ok": false, ...}`（例如沒有網路、沒有 git、遠端尚未打過任何 tag）：靜默略過，不告知使用者。
- 若 `update_available = true`：在稍後的回覆中簡短提醒一次即可，例如「（偵測到新版本 v{latest_version}，目前使用 v{current_version}，建議之後更新部署）」，不要中斷流程、不要因此停下來等使用者回應。

接著進行模型選擇（見下方「模型選擇流程」）。

模型選擇流程：
1. 讀取 <WORKSPACE_ROOT>/pbi_config/models_index.json，取得所有可用模型清單
2. 若只有一個模型 → 自動選定，告知使用者：「使用模型：{pbi_config_name}」
3. 若有多個模型 → 列出所有模型名稱供使用者選擇，等待使用者指定後繼續
4. 記住選定的 pbi_config_id，後續步驟皆使用此 ID
5. 依選定的 pbi_config_id 呼叫以下指令向 Server 取得該模型的 Access Token：

python "<SKILL_ROOT>/scripts/shared/fetch_credential.py" <pbi_config_id>

若執行失敗：向使用者說明「Access Token 取得失敗，請確認 PBI_MASK_KEY 是否正確；若金鑰無誤，可能是伺服器端（申請程式）的設定問題，請聯繫服務網址管理員協助排查」，並停止流程。
不要在回覆中逐字貼出 stderr 的原始錯誤內容——其中可能包含伺服器內部的識別碼、密鑰設定等基礎設施細節（例如 Azure AD App ID），不適合暴露給一般使用者；僅在使用者主動要求查看技術細節時才提供。
若執行成功，執行「模型概覽展示流程」（見下方），再詢問使用者：「您想查詢什麼？」

模型概覽展示流程：
1. 檢查「模型選擇流程」步驟 1 讀取 models_index.json 時，該模型的 model_description 欄位是否有值（申請程式管理員可預先為模型撰寫整體說明）。

若 model_description 有值（優先路徑，節省 token）：
直接以 model_description 作為模型概覽輸出，不需執行 model_overview.py、不需讀取 relationships/tables、不需自行分群或彙整量值——管理員撰寫的說明已涵蓋這些內容。輸出格式：

---
以下是 **{pbi_config_name}** 模型中可查詢的主要資料範圍：

{model_description}
---

若 model_description 為 null（回退路徑）：
執行以下指令取得該模型的整合結構化資料（relationships + 所有 tables），不要自行用 Read 工具逐一開啟 tables/ 目錄下的檔案，也不要委派給其他 Skill 或 subagent 處理：

python "<SKILL_ROOT>/scripts/shared/model_overview.py" "<WORKSPACE_ROOT>" "<pbi_config_id>"

若執行失敗，回報 stderr 錯誤訊息並停止流程。

直接使用上一步 stdout 回傳的 JSON（不需再讀取其他檔案，也不需另外委派任何 Skill 產生說明文件）中的 relationships、tables（與 Step 0 的 relationships.json／table_<表名>.json 內容相同），接著：
- 彙整每張資料表的 table 名稱、description、columns、measures 欄位
- 依資料表名稱與描述，以語意判斷將資料表分群（例如：訂單/銷售、客戶/會員、產品、庫存、經銷商等，依實際模型靈活命名）
- 彙整所有資料表中的 measures，列出名稱清單（不需列出 DAX 表達式）
- 以下列格式輸出模型概覽：

---
以下是 **{pbi_config_name}** 模型中可查詢的主要資料範圍：

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

書籤展示流程：
模型概覽輸出完之後、詢問「您想查詢什麼？」之前，取出該模型的查詢書籤。

**不需要再執行任何指令**——-1.1 的 preflight 已經帶回 `bookmarks.models`（依 pbi_config_id 分組），直接取 `bookmarks.models[<選定的 pbi_config_id>]` 即可（該 key 不存在代表這個模型還沒有書籤）。每筆為 `{"name", "request", "created_at", "updated_at"}`，已依 `updated_at` 由新到舊排序。

- 清單為空 → 不輸出任何書籤相關文字，直接進入提問。
- 清單非空 → 在模型概覽的**最下方**附上一段簡短清單（最多列 10 筆，超過時於結尾註明「（另有 N 筆，可請我列出全部）」）：

---
**已儲存的查詢書籤**
- 「{name}」：{request}
- ...

可以直接說書籤名稱重跑，或描述新的查詢需求。
---

只列名稱與需求描述，**不要列出 DAX 內容**（那會佔掉大量上下文）。
若 `bookmarks.persistent` 為 false，在清單後補一句：「（目前環境的檔案在對話結束後會清除，書籤僅在本次對話有效）」。

使用者指定要用某個書籤時，執行以下指令取得該書籤的 `dax` 與 `request`（清單本身不含 DAX，需要時才取）：

python "<SKILL_ROOT>/scripts/shared/bookmarks.py" show <pbi_config_id> "<name>"

並詢問使用者要用哪一種方式：
1. **直接執行存下的 DAX**——快，跳過 Step 0-4 的推理，直接進 Step 5。
2. **用原需求重新生成**——以書籤的 `request` 作為本次需求，正常走 Step 0.4-4 再進 Step 5；篩選設定檔或模型結構有變動時會反映最新狀態。

若書籤的 DAX 內含寫死的日期區間（例如 `>= DATE(2026,7,1)` 這類字面日期，而非 `TODAY()`/`EOMONTH()` 等相對日期函數），在詢問時主動提醒使用者：這個書籤的時間範圍是固定的，若想查最新期間請選擇「重新生成」。

Step 0：載入語意模型 (Load Semantic Model)
本地 pbi_config/<pbi_config_id>/ 資料夾存放由申請程式拆分並同步的語意模型 chunks，結構如下：
- pbi_config/<pbi_config_id>/relationships.json（全域關聯性，整個語意模型僅一份）
- pbi_config/<pbi_config_id>/tables/table_<表名>.json（各資料表結構，每張表一份）

此時應已於 -1.3 同步完成。若意外不存在（例如快取被手動清除），比照 -1.3 的 fetch_model.py 指令重新同步一次再繼續。

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
沿用 Step -1.1 偵測到的作業系統及 Step -1.3 模型選擇流程中記住的 <pbi_config_id>，執行以下對應指令：

python "<SKILL_ROOT>/scripts/shared/pbi_api_client.py" "<WORKSPACE_ROOT>" "<pbi_config_id>" "<WORKSPACE_ROOT>/pbi_query/dax_query.txt"

腳本執行成功後，會產生 pbi_query/query_result.csv。
腳本的標準輸出（stdout）會印出一行 JSON 摘要，格式如下：
{"success": true, "row_count": N, "csv_path": "pbi_query/query_result.csv"}

5.3 確認並回報結果
確認 pbi_query/query_result.csv 已成功產生後，向使用者回報：
- 查詢成功，共 N 筆資料
- 結果已輸出至：pbi_query/query_result.csv
- 詢問使用者：「是否需要 Claude 讀取並解讀此 CSV 資料？」

若腳本執行失敗，將 stderr 的錯誤訊息完整回報給使用者後停止。

5.4 詢問是否儲存為書籤
僅在查詢**成功**時詢問（失敗或零筆結果不問，那代表這個 DAX 還沒被驗證過）。若本次查詢是直接沿用既有書籤執行的，也不需要再問。

詢問：「要把這次的查詢存成書籤，下次直接重跑嗎？」
- 使用者不要 → 不做任何事，流程結束。
- 使用者要 → 詢問「這個查詢要叫什麼名稱？」，取得名稱後執行：

python "<SKILL_ROOT>/scripts/shared/bookmarks.py" save <pbi_config_id> "<名稱>" "<WORKSPACE_ROOT>/pbi_query/dax_query.txt" "<使用者本次的原始需求文字>"

DAX 一律由腳本從 `dax_query.txt` 讀取，**不要自己把 DAX 字串當作參數傳入、也不要用 Edit 工具手動改 bookmarks.json**——DAX 內含大量雙引號，手動轉義極易出錯。

若「書籤展示流程」列出的清單中已有同名書籤，先向使用者確認是否覆蓋，確認後再執行（腳本會直接覆蓋並在回傳中帶 `"overwritten": true`）。

回傳 JSON：{"success": true, "model_key": "...", "name": "...", "overwritten": bool, "persistent": bool, "proven": bool}
- `persistent` 為 true → 回覆「已儲存書籤『{name}』，下次執行 /nl-to-dax 時會出現在書籤清單中。」
- `persistent` 為 false → 回覆「已儲存書籤『{name}』（注意：目前環境的檔案在對話結束後會清除，此書籤僅適用本次對話；若要長期保存請改用 Claude Code CLI 或 VS Code 擴充功能）。」

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
