# CLAUDE.md — nl-to-dax 專案規則

## 版本控制規則

### 分支策略
- 依「憑證取得方式」維護三條長期分支，服務不同情境（不是短期 feature branch，各自直接在分支上提交，保持歷史線性）：
  - `solo`：自用模式，直接在 skill 內填 Azure AD `TENANT_ID`/`CLIENT_ID`/`CLIENT_SECRET`，不經過 Server；語意模型結構改用自製的 chunk_model + 說明產生 skill 取得，不依賴 `fetch_model.py`
  - `server-token`：集團模式現行方案，經 Server 註冊、核發 `PBI_MASK_KEY` 換 Access Token（過渡用，預期未來被 `mcp-oauth` 取代並合併回來）
  - `mcp-oauth`：集團模式下一代方案，改用 MCP connector + OAuth 認證，skill 完全不接觸任何憑證（開發完成並驗證後，預期合併回來取代 `server-token`）
- **Step 0～4**（識別資料表、驗證關聯、抽欄位量值、生成 DAX）與 `filters/` 篩選邏輯是三條分支共用的核心推理層，跟認證方式無關：
  - 這幾個 Step 的修改**一律先在 `solo` 分支進行**，驗證後再 merge/rebase 到 `server-token`、`mcp-oauth`
  - 嚴禁直接在 `server-token` 或 `mcp-oauth` 上修改這幾個 Step，避免三條分支各自分岔、日後難以合併
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
| `trigger_*.ps1 / *.sh` | 薄薄的 shell wrapper | 不含業務邏輯，只負責傳參給 Python |

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

### 跨平台相容性
- 新增腳本時三個平台（Windows / macOS / Linux）必須同步維護
- Windows 腳本使用 PowerShell，Unix 腳本使用 bash；共用邏輯下沉至 `scripts/shared/`
- 路徑分隔符號在 Python 內一律用 `os.path.join()`，不硬寫 `/` 或 `\`

---

## 開發計畫

> 完成的項目直接刪除。版本里程碑記錄請見 `.history`。
> 申請程式的開發計畫另立獨立專案追蹤。

### mcp-oauth 分支開放問題

> 此分支已完成 SKILL.md 骨架重構（Step -1 改為 MCP connector 認證檢查、模型選擇/概覽改呼叫 `list_models`、Step 5 改呼叫 `run_dax_query`），本機憑證管理腳本（`check_setup.py`、`fetch_credential.py`、`fetch_model.py`、`pbi_api_client.py`、`model_overview.py`、`skill_settings.py`）與對應 trigger 腳本已移除。以下項目待後端 MCP server 定案、或需要團隊一起拍板：

- **`list_models` 回傳內容範圍**：直接內含完整 `relationships`/`tables`，還是只回輕量清單（`pbi_config_id`/`pbi_config_name`/`model_description`/table 數），選定模型後再另外呼叫 `get_model_detail` 取得完整結構？後者對 token 成本較友善，尤其使用者可存取的模型數量多時。
- **查詢結果是否落地成本機 CSV 檔**：SKILL.md 目前預設維持落地（`pbi_query/query_result.csv`，由 Claude 用 Write 工具寫入），因為在 Claude Code 下寫檔案對使用者有意義；若之後主要在 Claude Apps sandbox 環境使用，寫了也是對話結束就消失，落不落地差異不大，需要重新評估。
- **`check_update.py`（Skill 版本檢查）去留**：維持現有比對 git tag 的機制，還是之後打包成 plugin 後改用 marketplace 自帶的版本機制？
- **`server-token` 分支的本機 `PBI_MASK_KEY` 流程要不要保留當 fallback**：會影響 SKILL.md 要不要維護兩條路徑（MCP 優先、本機憑證備援），需要跟後端一起決定。
- **實際串接測試**：上述 MCP 工具的參數/回傳格式需等後端 `list_models`/`get_model_detail`/`run_dax_query` 定案並在測試環境跑起來後，才能對照 SKILL.md 目前的暫定介面實際調整。

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
