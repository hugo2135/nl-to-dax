# CLAUDE.md — nl-to-dax 專案規則

## 版本控制規則

### 分支策略
- 單線 `main`，不開 feature branch
- 直接在 `main` 上提交，保持歷史線性

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

### 版號規則（Semantic Versioning）
- `breaking` commit → major 升版（v3 → v4）
- `feat` commit → minor 升版（v3.0 → v3.1）
- `fix` / `refactor` commit → patch 升版（v3.0.0 → v3.0.1）

### 打 Tag 時機
- 累積數個相關 commit 後，或完成一個明確功能里程碑時打 tag
- 不需要每個 commit 都打 tag
- 打 tag 前同步更新 `.history`

```bash
git tag v3.1.0
git push origin v3.1.0
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
- **憑證不明文存放**：所有連線資訊透過 JWT + `PBI_MASK_KEY` 驗證，設定檔本身不可讀
- **執行前必須驗證 JWT 過期時間**（`exp` 欄位），過期立即停止；Skill 端不驗簽名，僅 base64 decode payload
- **輸出 CSV 前先確保目錄存在**（`os.makedirs(..., exist_ok=True)`），避免路徑不存在導致靜默失敗

### 跨平台相容性
- 新增腳本時三個平台（Windows / macOS / Linux）必須同步維護
- Windows 腳本使用 PowerShell，Unix 腳本使用 bash；共用邏輯下沉至 `scripts/shared/`
- 路徑分隔符號在 Python 內一律用 `os.path.join()`，不硬寫 `/` 或 `\`

---

## 開發計畫

> 完成的項目直接刪除。版本里程碑記錄請見 `.history`。
> 申請程式的開發計畫另立獨立專案追蹤。

### 與申請程式的 API 合約

> 初版規格確認（2026-06-23）。實作指引更新，SERVER_JWT_SECRET 移除（2026-06-24）。Skill 開發期間以 mock server 對接。

**環境變數（設定至 `.claude/settings.local.json` 的 `env` 區塊，不使用系統環境變數）**

| 變數 | 用途 |
|------|------|
| `PBI_MASK_KEY` | 個人專屬金鑰，作為 API 請求的 Bearer token；使用者從管理後台領取 |
| `CREDENTIAL_SERVER_URL` | 申請程式的 base URL；正式 URL 待部署後填入 |

> `SERVER_JWT_SECRET` 已移除：Skill 端不驗 JWT 簽名，僅 base64 decode payload 取用欄位。
> 無需安裝任何第三方套件，`urllib` 標準函式庫即可完成所有 HTTP 呼叫（包含 Azure AD OAuth）。

**Skill 啟動流程（每次對話開始時執行）**

1. `GET /api/credential` → base64 decode JWT payload，取得連線資訊，快取至記憶體（提前 5 分鐘更新）
2. `GET /api/model` → 比對 `model_version`，若與快取版本相同則略過下載

**API 端點**

| 端點 | Header | 回傳 |
|------|--------|------|
| `GET /api/credential` | `Authorization: Bearer <PBI_MASK_KEY>` | `{"jwt": "<HS256 JWT>"}` |
| `GET /api/model` | `Authorization: Bearer <PBI_MASK_KEY>` | `{"model_version": N, "relationships": {...}, "tables": [...]}` |

**JWT Payload 欄位**：`tenant_id`, `client_id`, `client_secret`, `workspace_id`, `dataset_id`, `model_version`, `iss`, `iat`, `exp`

**快取策略**

| 資料 | 快取條件 | 更新時機 |
|------|---------|---------|
| credential | JWT 未過期（提前 5 分鐘更新） | 每次呼叫自動檢查 |
| model | `model_version` 未變動 | 管理員上傳新模型後自動失效 |

### v4.0.0 待辦

#### 重構：`pbi_api_client.py` 對齊新 API 合約

- 移除 `load_credentials()`（讀本地 JWT 檔）及 `SERVER_JWT_SECRET` 相關邏輯
- 改為呼叫 `GET /api/credential` 動態取得憑證，以 base64 decode payload 取用欄位（不驗簽名）
