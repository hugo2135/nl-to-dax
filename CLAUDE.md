# CLAUDE.md — nl-to-dax 專案規則

## 版本控制規則

### 分支策略
- 依「憑證取得方式」維護三條長期分支，服務不同情境（不是短期 feature branch，各自直接在分支上提交，保持歷史線性）：
  - `solo`：自用模式，直接在 skill 內填 Azure AD `TENANT_ID`/`CLIENT_ID`/`CLIENT_SECRET`，不經過 Server；語意模型結構改用自製的 chunk_model + 說明產生 skill 取得，不依賴 `fetch_model.py`
  - `server-token`：集團模式現行方案，經 Server 註冊、核發 `PBI_MASK_KEY` 換 Access Token（過渡用，預期未來被 `mcp-oauth` 取代並合併回來）
  - `mcp-oauth`：集團模式下一代方案，改用 MCP connector + OAuth 認證，skill 完全不接觸任何憑證（開發完成並驗證後，預期合併回來取代 `server-token`）
- **Step 0～4**（識別資料表、驗證關聯、抽欄位量值、生成 DAX）與篩選比對邏輯（Step 0.4）是三條分支共用的核心推理層，跟認證方式無關：
  - 這幾個 Step 的修改**一律先在 `solo` 分支進行**，驗證後再 merge/rebase 到 `server-token`、`mcp-oauth`
  - 嚴禁直接在 `server-token` 或 `mcp-oauth` 上修改這幾個 Step，避免三條分支各自分岔、日後難以合併
  - **例外**：Step 0.4 的篩選規則「比對演算法」（收集預設篩選、比對 contextKeywords、決定最終篩選集）三分支共用；但「資料來源」是各分支專屬——`solo`/`server-token` 讀本機 `filters/*.json`，`mcp-oauth` 改讀 `get_model_detail` 回傳的 `filters` 欄位（管理員於申請程式 `/admin/pbi-configs` 集中維護）。`mcp-oauth` 已移除本機 `filters/` 資料夾。
- **Step -1**（環境檢查與認證取得）、**Step 5**（執行查詢的認證串接）是各分支專屬邏輯，不受上述共用限制，各自獨立維護

### Commit 訊息格式（Conventional Commits）
```
<type>: <簡短描述>
```

| type | 使用時機 |
|------|---------|
| `feat` | 新功能（新篩選設定檔、新模式、新腳本） |
| `fix` | Bug 修正 |
| `refactor` | 不影響行為的程式碼重構 |
| `docs` | README、.history、CLAUDE.md 等文件更新 |
| `chore` | 設定檔、.gitignore 等雜項 |
| `breaking` | 破壞性變更（需升 major 版號） |

範例：
```
feat: 新增退費訂單篩選設定檔
fix: 修正 Windows 路徑定位在無 .claude 目錄時的錯誤
breaking: 重構 JWT 憑證格式，payload 欄位名稱變更
```

### 版號規則（Major.Build）
- `breaking` commit → major 升版，build 歸零（0.1 → 1.0）
- `feat` / `fix` / `refactor` commit → build 遞增（0.1 → 0.2）

不分 minor/patch：這個 skill 沒有外部套件依賴者需要鎖版本範圍，版號唯一的用途是讓 skill 自己判斷「有沒有新版本」，只需要區分「破壞性變更」跟「其餘所有變更」兩級即可。

### 打 Tag 時機
- 累積數個相關 commit 後，或完成一個明確功能里程碑時打 tag
- 不需要每個 commit 都打 tag
- 打 tag 前同步更新 `.history` 與 `nl-to-dax/VERSION`（兩者版號必須一致，`VERSION` 是 skill 自動檢查更新時比對的依據）

```bash
git tag v0.2
git push origin v0.2
```

---

## 檔案規則

- `pbi_credentials.jwt` 絕對不進版本控制
- `pbi_query/` 是執行期暫存目錄，不進版本控制
- 新增篩選設定檔時，同步更新 `README.md` 的篩選說明表格
- 版本升級時，同步更新 `.history`

---

## 工程原則

### 解耦設計
各元件職責單一，互不知道彼此的存在：

| 元件 | 唯一職責 | 不應該做的事 |
|------|---------|-------------|
| `chunk_model.py` | 拆分語意模型 JSON | 不知道 DAX、不知道 API |
| `pbi_api_client.py` | 呼叫 Power BI REST API | 不知道篩選邏輯、不知道模型結構 |
| `filters/*.json` | 宣告業務規則篩選條件 | 不含任何程式邏輯 |
| `preflight.py` | 啟動檢查的編排層 | 不含檢查邏輯本身，只呼叫各腳本並組裝成單一 JSON |

**原則：新增業務規則優先考慮新增設定檔，而非修改程式碼。**

### Python 編碼規範
- 只使用 Python 標準函式庫，禁止引入 `requests`、`pandas` 等第三方套件
- `stdout` 保留給 JSON 摘要（供 Skill 解析），使用者可讀的進度與錯誤訊息一律寫 `stderr`
- 檔案讀寫一律明確指定 `encoding='utf-8'`；輸出 CSV 使用 `utf-8-sig`（Excel 相容）
- 腳本開頭必須設定 `sys.stdout.reconfigure(encoding='utf-8')`
- 不寫死任何絕對路徑，一律透過 `.claude/` 作為基準，同一層是工作區，子階層只涉及`.claude/skills/nl-to-dax`

### Power BI REST API 使用政策
- **不實作 retry**：API 失敗時完整回報 HTTP status code 與 response body，由使用者判斷後續行動
- **Azure AD OAuth 由 Server 統一處理**：Skill 端不持有 tenant_id / client_id / client_secret，直接使用 `/api/token` 回傳的 access_token
- **執行前警告 Token 過期**（比對 `expires_at`），過期時印 stderr 警告後仍嘗試執行；若 Power BI 回 401 則提示重新執行 `fetch_credential.py`
- **輸出 CSV 前先確保目錄存在**（`os.makedirs(..., exist_ok=True)`），避免路徑不存在導致靜默失敗

### 已定案的設計決策（不需要再重新討論）
- **查詢書籤永久留在本機**（`<SKILL_ROOT>/config/bookmarks.json`），不做 Server 端書籤 API。
  理由不是伺服器資源——書籤只有幾 KB、寫入頻率極低，成本相較於每次對話都要傳的
  `get_model_detail`（實測約 95KB）根本是雜訊——而是**職責歸屬**：篩選規則／查詢模式／
  欄位別名是管理員定義的業務規則，必須集中治理；「我存的查詢」則是個人工作狀態，
  放本機才符合歸屬，同時不新增失效點（Server 掛掉書籤照常可用），也不讓 Server
  累積「誰在追什麼問題」這類隱私資訊。
  **代價是永久性的、不是待補缺口**：Claude Apps 的沙盒每次對話清空，該環境下書籤只在
  當次對話有效。SKILL.md 與 README 已明確告知並建議改用 Claude Code CLI／VS Code
  擴充功能長期保存，措辭不需再改。

### 敏感值傳遞規則
- **access token 絕對不能經過 Claude**，一律由腳本自己去換、自己用：`mcp-oauth` 是拿一次性 `ticket` 交給 `execute_dax_query.py`，由腳本自行 POST `redeem_url` 換成 token 後直接呼叫 Power BI；`solo`／`server-token` 則是腳本自己讀本機憑證檔換 token。Claude 只負責傳遞 ticket 或觸發腳本，從不接觸 token 本身
  - 曾經試過「Claude 呼叫 tool 拿到 token → 寫成暫存檔 → 傳路徑給腳本」，看起來 token 沒進命令列，但 `Write` 工具的內容一樣會完整顯示在呼叫端 UI 與對話上下文——沒有解決根本問題，只要 token 回到 Claude 手上就一定會被顯示
  - 低價值、短效、單次使用的憑證（例如 300 秒過期的 ticket）當命令列參數傳沒問題，外流時已無利用價值
  - 若腳本仍需暫存憑證到磁碟（例如舊架構的 mask key），刪除必須放在 `try/finally`，確保任何錯誤路徑都不會讓機密殘留

### 跨平台相容性
- **不使用 shell wrapper**：所有腳本一律由 Claude 直接以 `python`（Windows）／`python3`（macOS/Linux）呼叫，全部放在 `scripts/shared/`，不再維護 `scripts/windows|macos|linux/` 的 `.ps1`/`.sh` 觸發腳本。
  - 原因一：Windows 用戶端版的 PowerShell ExecutionPolicy 預設是 `Restricted`，會直接擋掉未簽署的 `.ps1`（實測確認），等於 wrapper 自己製造了一個直接呼叫 Python 不會有的失敗點。
  - 原因二：那些 wrapper 內容只是 `python <絕對路徑> $args`，而 SKILL.md 本來就要分平台決定呼叫哪一個，連「封裝 python/python3 差異」的價值都沒有。
  - 兩種呼叫方式對 `import` 解析沒有差異：Python 會把**腳本自身所在目錄**放進 `sys.path`，與工作目錄無關（實測從 `C:\Windows` 執行仍正常）。
- 路徑分隔符號在 Python 內一律用 `os.path.join()`，不硬寫 `/` 或 `\`；SKILL.md 內的指令範例統一寫 `/`（Windows 的 Python 同樣接受）
- 啟動檢查一律加進 `preflight.py`，不要新增第二支需要 Claude 另外呼叫的檢查腳本
- **`preflight.py` 的版本閘門必須維持在其餘 `import` 之前**：它負責回報「Python 版本夠不夠」，若在頂層就 import 其他模組，而那些模組用到較新語法（例如 PEP 604 的 `str | None` 需要 3.10+），使用者拿到的會是 traceback 而不是「請升級 Python」

---

## 開發計畫

> 完成的項目直接刪除。版本里程碑記錄請見 `.history`。
> 申請程式的開發計畫另立獨立專案追蹤。

### mcp-oauth 分支開放問題

> 此分支已完成 SKILL.md 骨架重構，本機憑證管理腳本（`check_setup.py`、`fetch_credential.py`、`fetch_model.py`、`pbi_api_client.py`、`model_overview.py`、`skill_settings.py`）與對應 trigger 腳本已移除。後端已提供正式的 MCP 工具定義（`list_models`、`get_model_detail`、`get_query_ticket`，見下方架構說明），SKILL.md 已依此更新，不再是暫定介面。

**架構確認（跟最初假設不同，記錄避免之後又搞錯）**：Server 端**不提供執行查詢的 MCP 工具**。DAX 查詢是 Skill 自己直接對 Power BI 的 `executeQueries` REST API 發送請求（`scripts/shared/execute_dax_query.py`），不經過 nl-to-dax 的 Server——這是刻意設計，避免多使用者併發查詢時卡住 Server 的同步呼叫。

**查詢授權採一次性 ticket**（2026-08 上線，取代最初的 `get_powerbi_token` 直接回傳 token 設計）：`get_query_ticket(pbi_config_id)` 回傳單次使用、預設 300 秒效期的 `ticket` 與 `redeem_url`；**兌換成 access token 的動作在 `execute_dax_query.py` 內部完成**，token 只存在該行程的記憶體，不進對話上下文、不進命令列、不落地。
- **token 快取指引與舊設計相反**：ticket 單次使用，每次查詢前都要重新呼叫 `get_query_ticket`，不快取。
- **過期重試是必要路徑，不是選配**：Bash 執行前的權限確認等待會算進 ticket 效期，使用者稍微離開就可能過期。腳本兌換回 401 時輸出 `"ticket_expired": true`，Skill 據此重新取票後重跑一次（上限一次）。SKILL.md 因此要求**先寫 `dax_query.txt` 再取票**，重試時不需重新生成 DAX。
- Network egress 需放行兩個網域：`api.powerbi.com`（執行查詢）與申請程式網域（兌換 ticket）。

已解決：
- ~~`list_models` 回傳範圍~~：確認為輕量清單（`pbi_config_id`/`pbi_config_name`/`model_version`/`model_description`/`table_count`/`query_modes`），完整 `relationships`/`tables`/`workspace_id`/`dataset_id`/`filters`/`column_aliases` 由獨立的 `get_model_detail(pbi_config_id, mode_id?)` 取得。
- ~~`server-token` 分支要不要保留當 fallback~~：後端已明確表示新舊 skill 一律統一改用 MCP，**不維護兩條並行路徑**，`server-token` 分支維持原規劃（過渡用，之後合併回來取代）。
- ~~`get_powerbi_token` → `get_query_ticket` 遷移~~：已於 2026-08 實測驗證完整路徑——`get_powerbi_token` 確認回 `Unknown tool`（MCP connector 需重新連線才會生效）、`get_query_ticket` 回傳格式與 SKILL.md 描述一致、`execute_dax_query.py` 兌換並執行查詢成功、重複使用同一張 ticket 正確觸發 `ticket_expired`。
- ~~`query_modes`/`column_aliases` 實際驗證~~：已於 2026-08 實測 `list_models`/`get_model_detail` 確認兩個欄位皆已回傳（目前既有模型未設定 query_modes/column_aliases 內容，但欄位結構已到位，純增量邏輯不受影響）。

仍待確認：
- **查詢結果是否落地成本機 CSV 檔**：SKILL.md 目前預設維持落地（`pbi_query/query_result.csv`，由 Claude 用 Write 工具寫入），因為在 Claude Code 下寫檔案對使用者有意義；若之後主要在 Claude Apps sandbox 環境使用，寫了也是對話結束就消失，落不落地差異不大，需要重新評估。
- **`check_update.py`（Skill 版本檢查）去留**：維持現有比對 git tag 的機制，還是之後打包成 plugin 後改用 marketplace 自帶的版本機制？跟認證機制無關。

### 與申請程式的 API 合約

> 初版規格確認（2026-06-23）。SERVER_JWT_SECRET 移除（2026-06-24）。/api/token 架構確認（2026-07-06）：Server 統一處理 Azure AD OAuth，Skill 端只需 access_token。

**環境變數（設定至 `.claude/settings.local.json` 的 `env` 區塊，不使用系統環境變數）**

| 變數 | 用途 |
|------|------|
| `PBI_MASK_KEY` | 個人專屬金鑰，作為 API 請求的 Bearer token；使用者從管理後台領取 |
| `CREDENTIAL_SERVER_URL` | 申請程式的 base URL；正式 URL 待部署後填入 |

> Azure AD OAuth 完全由 Server 處理，Skill 端不持有任何 Azure 憑證。無需安裝任何第三方套件，`urllib` 標準函式庫即可完成所有 HTTP 呼叫。

**Skill 啟動流程（每次對話開始時執行）**

1. `GET /api/models` → 取得所有可用模型清單（含 model data）；比對 `model_version`，版本未變則沿用本地快取
2. 若使用者有多個可用模型，詢問要查詢哪個；單一模型則自動選定
3. `GET /api/token?pbi_config_id=<id>` → Server 向 Azure AD 換取 access_token 後回傳，Skill 直接使用

**API 端點**

| 端點 | Header | 說明 |
|------|--------|------|
| `GET /api/models` | `Authorization: Bearer <PBI_MASK_KEY>` | 回傳所有可用模型（含 relationships、tables、model_version） |
| `GET /api/token?pbi_config_id=<id>` | `Authorization: Bearer <PBI_MASK_KEY>` | Server 換取 Azure AD access_token 後回傳，含 workspace_id、dataset_id |

**`/api/models` 回傳格式**
```json
{
  "models": [
    {
      "pbi_config_id": "<uuid>",
      "pbi_config_name": "顯示名稱",
      "model_version": 5,
      "relationships": { "relationships": [...] },
      "tables": [...]
    }
  ]
}
```

**`/api/token` 回傳格式**
```json
{
  "access_token": "<bearer-token>",
  "token_type": "Bearer",
  "expires_in": 3599,
  "workspace_id": "<uuid>",
  "dataset_id": "<uuid>",
  "model_version": 5
}
```

**本地快取結構**

```
.claude/
└── pbi_configs.json                     ← {<pbi_config_id>: {access_token, workspace_id, dataset_id, expires_at, model_version}}

pbi_query/
├── models_index.json                    ← [{pbi_config_id, pbi_config_name, model_version, table_count}]
├── <pbi_config_id>/
│   ├── relationships.json
│   └── tables/
│       └── table_<表名>.json
└── query_result.csv
```

> `pbi_configs.json` 存放敏感的 access token，受 `.gitignore` 的 `.claude` 規則保護。`pbi_query/` 只存放不敏感的模型結構與查詢結果。

**快取策略**

| 資料 | 快取條件 | 更新時機 |
|------|---------|---------|
| models | 各模型的 `model_version` 未變動 | 管理員上傳新模型後自動失效 |
| access token | `expires_at` 未過期（fetch 時 +expires_in 換算） | 過期後重新執行 fetch_credential.py |
