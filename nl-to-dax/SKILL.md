---
name: nl-to-dax
description: 根據使用者以中文或英文描述的自然語言需求，透過多階段推理生成適用於 Power BI REST API 的專用 DAX 查詢語法，透過 nl-to-dax MCP connector 取得語意模型與 Access Token 後直接查詢 Power BI 並輸出結果。當使用者想要查詢 Power BI 語意模型中的資料、要求產生 DAX 查詢、或提到「查訂單」「查銷量」等業務資料查詢需求時，使用此 skill。
---

# Natural Language to DAX Skill（mcp-oauth 分支）

輸入
執行此 Skill 時，使用者需提供 DAX 需求：以中文或英文描述想查詢的資料內容或計算邏輯。

執行步驟

Step -1：認證檢查 (Auth Check)

此 SKILL.md 所在的目錄即為 Skill 根目錄，以下稱 <SKILL_ROOT>。

用 Read 工具讀取 <SKILL_ROOT>/config/site_domain.json 的 `site_domain` 欄位，取得申請程式網域，以下稱 <SITE_DOMAIN>。檔案不存在代表部署未完成，這不是使用者能自行處理的事：僅告知使用者「請聯繫管理員協助」，流程到此停止。

嘗試呼叫 MCP 工具 `list_models`（無參數），取得使用者目前有權限存取的語意模型清單（輕量版，不含完整 relationships/tables）。

若呼叫失敗（尚未連接 MCP connector 或授權已過期），向使用者說明（MCP 的 OAuth 登入畫面不會繞過帳號審核，未完成申請流程登入畫面會直接失敗，需完整說明）：

「這個 Skill 需要先連接 nl-to-dax 的 MCP connector。若您使用的 AI App 支援 Settings → Connectors 這類 OAuth 連線介面（例如 Claude Code、Claude Apps）：
1. 若還沒有帳號則前往 [{SITE_DOMAIN}](https://{SITE_DOMAIN}/register) 註冊
2. 通知並等待管理員開通帳號
3. 帳號開通後，請新增MCP Server
  - 名稱：nl-to-dax_credential-server
  - URL：https://{SITE_DOMAIN}/mcp
  等待自動開啟頁面後申請好的帳密登入
4. 重新執行 /nl-to-dax。(如果使用CLI則需要重開對話)

若您使用的 AI App 不支援 OAuth 連線畫面（沒有 Settings → Connectors 這類介面，需自行寫 MCP Server 設定檔）：
1. 若還沒有帳號則前往 [{SITE_DOMAIN}](https://{SITE_DOMAIN}/register) 註冊
2. 通知並等待管理員開通帳號
3. 帳號開通後，登入 [{SITE_DOMAIN}](https://{SITE_DOMAIN}/)，新增一組 MCP 用 token
4. 依您使用的 AI App 規範，用此 token 建立 MCP Server 設定（URL：https://{SITE_DOMAIN}/mcp）
5. 重新執行 /nl-to-dax
」

流程到此停止。

若呼叫成功：回傳內容為 `list[dict]`，每筆至少包含 `pbi_config_id`、`pbi_config_name`、`model_version`、`model_description`（可能為 null）、`table_count`。直接進入「模型選擇流程」。

（可選）Skill 版本檢查：
與認證機制無關，是否保留現有 `check_update.py`、或改用未來 plugin marketplace 自帶的版本機制，屬於獨立的開放問題（見 CLAUDE.md 開發計畫），不影響本節主流程。若保留，執行方式：

macOS / Linux：
python3 "<SKILL_ROOT>/scripts/shared/check_update.py"

Windows（PowerShell）：
python "<SKILL_ROOT>\scripts\shared\check_update.py"

回傳 JSON：{"current_version": "...", "latest_version": "..."|null, "update_available": bool, "checked": bool}
此步驟純粹是提醒性質：執行失敗或 checked = false 時靜默略過，不告知使用者；`update_available = true` 時在稍後的回覆中簡短提醒一次即可，不中斷流程。

模型選擇流程：
1. 從 `list_models` 回傳的清單中選擇模型
2. 若只有一個模型 → 自動選定，告知使用者：「使用模型：{pbi_config_name}」
3. 若有多個模型 → 列出所有模型名稱供使用者選擇，等待使用者指定後繼續
4. 記住選定的 `pbi_config_id`，後續步驟皆使用此 ID
5. 呼叫 MCP 工具 `get_model_detail(pbi_config_id)`，取得 `relationships`、`tables`、`workspace_id`、`dataset_id`、`filters`（Step 0.4 篩選規則）。**不論 `model_description` 有沒有值都要呼叫**——Step 0-5 都需要這裡的資料，只呼叫這一次、後續複用。
   - 若使用者沒有該 `pbi_config_id` 的存取權，此工具會回傳 tool error，向使用者說明「無法取得此模型的存取權限，請聯繫管理員確認」，停止流程。
6. 記住 `workspace_id`、`dataset_id`，Step 5 會用到。
7. 執行「模型概覽展示流程」（見下方），再詢問使用者：「您想查詢什麼？」

模型概覽展示流程：
使用上一步 `get_model_detail` 已取得的資料，檢查該模型的 `model_description` 欄位是否有值（申請程式管理員可預先為模型撰寫整體說明）。

若 model_description 有值（優先路徑，節省產生概覽文字的推理成本）：
直接以 model_description 作為模型概覽輸出，不需自行分群或彙整量值——管理員撰寫的說明已涵蓋這些內容。輸出格式：

---
以下是 **{pbi_config_name}** 模型中可查詢的主要資料範圍：

{model_description}
---

若 model_description 為 null（回退路徑）：
使用 `get_model_detail` 回傳的 `tables` 資料：
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

Step 0：載入語意模型結構 (Load Semantic Model)

「模型選擇流程」已取得 relationships 與 tables，不需要再另外呼叫工具。資料格式如下：

表與表關聯（relationships）：

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

表與行和量值（tables 陣列中每個 table 物件）：

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

Step 0.4：載入並比對篩選設定檔 (Load & Match Filter Profiles)
使用「模型選擇流程」呼叫 `get_model_detail` 時已取得的 `filters` 欄位（陣列，管理員於申請程式 `/admin/pbi-configs` 集中維護，不再讀本機檔案）。每筆設定的結構如下：

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

Step 1：識別所需資料表
仔細閱讀使用者的自然語言需求。
當需求中出現模糊詞彙時，必須先中斷流程，向使用者確認猜測，待使用者明確回覆後才能繼續。

根據需求中的語意關鍵字，從已取得的模型結構中，初步盲推/判斷哪些「資料表」是回答該問題的核心主角。

Step 2：驗證表傳遞與關聯
開啟 「表與表關聯」資料。

檢查 Step 1 選出的多張資料表之間，其關聯性是否有效（檢查 isActive 是否為 true、傳遞方向 crossFilterDirection 以及基數 cardinality 是否能支撐篩選邏輯）。

【發問機制】：若發現表之間沒有關聯、關聯斷掉，或使用者需求語意模糊，此時必須中斷流程，先向使用者發問確認，待確認 OK 後才能進入下一步。

Step 3：提取精準欄位與量值
關聯確認無誤後，針對確認需要的資料表，精準開啟對應的 「表與行和量值」資料。

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

> 查詢結果是否落地成本機 CSV 檔案是開放問題（見 CLAUDE.md 開發計畫），本節先以「維持落地」為預設行為，之後依團隊決定調整。

Server 只提供 `get_powerbi_token` 換發 token，DAX 查詢由 Skill 自己直接對 Power BI 的 `executeQueries` API 發送（架構原因見 CLAUDE.md 開發計畫）。

5.1 取得 Access Token（對話內快取，避免重複呼叫）
檢查本次對話中，選定的 `pbi_config_id` 是否已經有尚未過期的 access token（記住上次取得的時間點與 `expires_in`，預留 1-2 分鐘安全邊界）：
- 有效 → 直接複用，跳到 5.2
- 沒有或已過期 → 呼叫 MCP 工具 `get_powerbi_token(pbi_config_id)`，取得新的 `access_token`/`expires_in`，記住取得時間

若 `get_powerbi_token` 失敗 ：向使用者說明「Access Token 取得失敗，請聯繫管理員處理」，停止流程。不要逐字暴露 tool error 的原始錯誤內容給一般使用者（可能包含基礎設施細節），僅在使用者主動要求查看技術細節時才提供。

**此 access token 只能存在於本次對話的上下文中，絕對不可以寫入任何本機檔案跨對話持久化。**

5.2 執行查詢
使用 Write 工具，將 Step 4 產生的完整 DAX 查詢語法（不含程式碼區塊標記）寫入使用者目前工作目錄下的 `pbi_query/dax_query.txt`（使用絕對路徑）。

執行以下指令（`<SKILL_ROOT>` 替換為實際路徑，`workspace_id`/`dataset_id` 來自「模型選擇流程」步驟 5 的 `get_model_detail` 回傳）：

macOS / Linux：
python3 "<SKILL_ROOT>/scripts/shared/execute_dax_query.py" "<access_token>" "<workspace_id>" "<dataset_id>" "<dax_query.txt 的絕對路徑>" "<pbi_query/query_result.csv 的絕對路徑>"

Windows（PowerShell）：
python "<SKILL_ROOT>\scripts\shared\execute_dax_query.py" "<access_token>" "<workspace_id>" "<dataset_id>" "<dax_query.txt 的絕對路徑>" "<pbi_query\query_result.csv 的絕對路徑>"

回傳 JSON 格式：{"success": true, "row_count": N, "csv_path": "..."}

若執行失敗：將 stderr 的錯誤訊息回報給使用者（此腳本執行在使用者自己的環境中，不像 Step -1 的 MCP tool error 可能包含伺服器端基礎設施細節，可以完整呈現），停止流程。

5.3 回報結果
若執行成功，向使用者回報：
- 查詢成功，共 N 筆資料
- 結果已輸出至：`pbi_query/query_result.csv`
- 詢問使用者：「是否需要 Claude 讀取並解讀此 CSV 資料？」

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
