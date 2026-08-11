# nl-to-dax（server-token 分支）

自然語言轉 DAX 查詢的 Claude Code Skill，針對 Power BI REST API 設計。輸入需求描述，自動完成環境初始化、模型同步、關聯驗證、篩選套用，直接呼叫 API 並輸出 CSV 結果。語意模型由申請程式集中管理，首次使用自動同步至本地。

> 本倉庫為內部部署版本：`config/default_credential_server_url.txt` 已預先填好服務網址，使用者只需要申請個人的 `PBI_MASK_KEY`，不需要另外詢問管理員網址。

---

## 分支說明

此 Skill 依「憑證取得方式」維護三條分支，服務不同情境：

| 分支 | 適用情境 | 認證方式 |
|------|----------|----------|
| `solo` | 自用／個人使用，不經過集中管理的 Server | 直接在 Skill 內填寫 Azure AD Tenant ID / Client ID / Client Secret |
| `server-token` | 集團／多人使用，舊方案 | 向 Server 申請 `PBI_MASK_KEY`，換取 Access Token |
| `mcp-oauth` | 集團／多人使用，現行方案 | MCP connector + OAuth，Skill 不接觸任何憑證 |

以下內容說明的是**本分支（`server-token`）**的安裝與使用方式。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 自動初始化 | 啟動時檢查環境，自動建立設定檔（服務網址已預填）並引導完成金鑰申請流程 |
| 多模型支援 | 支援多個 Power BI 資料集，啟動時列出可用模型供選擇 |
| 模型概覽展示 | 取得 Token 後自動彙整模型中的資料表與量值，讓使用者了解可查詢範圍 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 直接執行 | Server 統一處理 Azure AD 驗證，Skill 直接使用 access token 執行查詢並輸出 CSV |
| 查詢書籤 | 查詢成功後可命名存檔，下次執行時列在模型概覽最下方，可直接重跑或用原需求重新生成 |
| 版本提醒 | 每日至多檢查一次是否有新版本，有更新時簡短提醒，不中斷使用 |
| 環境自檢 | 啟動時一次檢查 Python 版本、設定狀態、版本更新與書籤，異常時清楚告知原因 |
| 每日模型重新同步 | 管理員異動使用者的已分配模型後，最晚隔天即自動重新同步，不會卡在舊清單 |

---

## 前置條件

- Python 3.9+（無需額外安裝第三方套件，僅使用標準函式庫）
- **Claude Code CLI 或 VS Code + Claude Code 擴充功能**（不支援 Claude 桌面版／Cowork／claude.ai 網頁版：這些介面的 skill 執行環境是每次對話重新產生的暫存沙盒，設定檔無法持續保存，會導致每次都要重新設定 `PBI_MASK_KEY`）
- Git（版本提醒功能需要，用於查詢遠端最新版號；未安裝或無法連線時會靜默略過，不影響其他功能）

---

## 安裝 Skill

把整個 `nl-to-dax/` 目錄放進 Claude Code 會讀取的 skill 路徑，以下兩種位置都支援：

- **專案內安裝**：`<你的專案>/.claude/skills/nl-to-dax/` — 只在這個專案生效
- **使用者層級安裝**：`~/.claude/skills/nl-to-dax/` — 對所有專案生效

兩種安裝方式行為完全一致，Skill 會自動判斷目前工作的專案目錄，不需要額外設定。

---

## 初次設定

### 步驟一：執行 Skill 觸發自動建檔

在 Claude Code 中輸入 `/nl-to-dax`：

- Skill 自動建立 `<SKILL_ROOT>/config/settings.local.json`（`CREDENTIAL_SERVER_URL` 已預填本倉庫設定的服務網址，`PBI_MASK_KEY` 留空）
- 提示您前往服務網址完成註冊，取得個人專屬的 `PBI_MASK_KEY`

### 步驟二：申請帳號並取得金鑰

1. 點選「立即註冊」，填入 Email 與密碼後送出申請
2. 等待管理員開通帳號
3. 開通後登入，進入個人頁面點選「領取 PBI_MASK_KEY」
4. 金鑰只顯示一次，請立即複製並妥善保存

### 步驟三：填入金鑰並重新執行

取得金鑰後，可以直接提供給 Claude 代為寫入設定檔，或自行編輯 `settings.local.json` 填入 `PBI_MASK_KEY`。完成後重新執行 `/nl-to-dax`，Skill 會自動同步語意模型並取得 Access Token。

> **注意**：金鑰為個人專屬，僅能領取一次；遺失請聯絡管理員重設。

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                          # Skill 主體目錄（<SKILL_ROOT>）
│   ├── SKILL.md                        # Skill 執行指令（Claude 讀取）
│   ├── VERSION                         # 目前版號（major.build，例如 0.1）
│   ├── config/
│   │   ├── default_credential_server_url.txt   # 本倉庫預設服務網址（settings.local.json 首次建立時帶入）
│   │   └── update_source.json.example          # 版本檢查的來源倉庫，複製為 update_source.json 並填入 repo_url
│   ├── filters/                        # DAX 篩選設定檔
│   │   ├── default_order.json          # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json          # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json        # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       └── shared/                     # 跨平台共用 Python 腳本（由 Claude 直接以 python 呼叫，無 shell wrapper）
│           ├── preflight.py            # 啟動前置檢查：一次回傳 Python 環境／設定狀態／版本更新／查詢書籤
│           ├── skill_settings.py       # 共用工具：skill_root/workspace_root 判斷、設定檔讀寫
│           ├── bookmarks.py            # 查詢書籤的存取（list/show/save/delete）與環境持久性偵測
│           ├── check_setup.py          # 環境檢查（回傳 JSON 狀態，含每日模型同步旗標）
│           ├── check_update.py         # 每日版本檢查（比對遠端 git tag）
│           ├── fetch_credential.py     # 向申請程式取得 Access Token
│           ├── fetch_model.py          # 向申請程式同步語意模型，並清除已收回權限的舊快取
│           ├── model_overview.py       # 彙整單一模型的 relationships + tables，供模型概覽使用
│           └── pbi_api_client.py       # Power BI REST API 客戶端
└── README.md
```

執行期間自動產生（皆已納入 `.gitignore`）：

```
<SKILL_ROOT>/config/
├── settings.local.json           # PBI_MASK_KEY 與服務網址（敏感）
├── pbi_configs.json              # Access Token 快取（敏感）
├── bookmarks.json                # 查詢書籤（依模型分組）
└── env_probe.json                # 判斷本機檔案能否跨對話存活的探針

<你的工作區根目錄>/
├── pbi_config/                   # 語意模型快取（fetch_model.py 同步而來，跨查詢重複使用）
│   ├── models_index.json         # 可用模型清單
│   ├── last_sync.json            # 上次成功同步日期，決定是否需要每日重新同步
│   └── <pbi_config_id>/
│       ├── relationships.json    # 資料表關聯性
│       └── tables/
│           └── table_<表名>.json # 各資料表結構（含量值定義）
└── pbi_query/                    # 每次查詢的暫存產物（用完即可清除）
    ├── dax_query.txt             # 本次生成的 DAX 查詢
    └── query_result.csv          # 查詢結果
```

> `pbi_config/` 存放的是模型結構快取，`pbi_query/` 只存放單次查詢的輸入/輸出，兩者職責分開。

---

## 使用方式

在 Claude Code 中輸入 `/nl-to-dax`，描述您想查詢的資料需求（中英文皆可）：

```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 自動完成：環境初始化（Python 檢查）→ 版本檢查 → 模型清單同步（每日至多一次）→ 模型選擇 → 模型概覽展示 → DAX 生成 → API 執行 → CSV 輸出。

---

## 篩選設定檔

篩選設定檔（`filters/*.json`）用於在生成 DAX 時自動套用業務規則篩選條件。

| 設定檔 | 常態啟用 | 觸發關鍵字 | 說明 |
|--------|----------|------------|------|
| `default_order.json` | 是 | — | 排除倉庫調撥、退費、取消等非銷售訂單 |
| `investigation.json` | 否 | 排查、調查、異常、debug… | 覆蓋預設篩選，顯示完整資料 |
| `refund_analysis.json` | 否 | 退費、退款、refund… | 覆蓋預設篩選，僅顯示退費相關訂單 |

新增篩選設定檔只需在 `filters/` 資料夾中新增符合格式的 JSON 檔，Skill 會在下次執行時自動載入。

---

## 查詢書籤

查詢成功後，Skill 會問您要不要把這次的 DAX 存成書籤並命名。之後每次執行 `/nl-to-dax`，選定模型後的模型概覽最下方就會列出該模型已存的書籤，可以直接說名稱重跑。

書籤會同時存下 **DAX** 與**當初的自然語言需求**，重用時提供兩個選項：

- **直接執行**：跳過推理步驟，最快、最省 token
- **用原需求重新生成**：重新走一次 DAX 生成流程，會套用最新的篩選設定檔與模型結構

之所以保留第二個選項，是因為存下的 DAX 是「凍結」的——如果當初生成的是寫死的日期區間（而非 `TODAY()` 這類相對日期函數），或之後 `filters/` 的篩選規則、管理員維護的語意模型有調整，直接重跑會得到過時的結果。Skill 偵測到書籤含字面日期時會主動提醒。

書籤存在 `<SKILL_ROOT>/config/bookmarks.json`，依模型的 `pbi_config_id` 分組，所以不同模型的書籤不會互相混淆。

---

## 輸出結果

每次執行輸出以下三項：

- DAX 查詢語法（程式碼片段）
- 使用到的欄位與量值清單
- `pbi_query/query_result.csv`（查詢結果）及執行摘要（筆數回報）

---

## 版本更新

每次執行時，Skill 每日最多向遠端倉庫查詢一次最新版號（比對 git tag），若偵測到有更新版本會簡短提醒一次，不會中斷查詢流程。要更新到最新版本，請重新取得本倉庫最新內容並覆蓋部署路徑。

需要在 `<SKILL_ROOT>/config/update_source.json` 填好來源倉庫才會啟用（複製 `update_source.json.example` 並填入 `repo_url`，SSH／HTTPS 皆可，走本機既有的 git 憑證）。沒設定的話整個檢查會靜默略過，不影響其他功能。

三條分支共用同一個倉庫、也就共用同一個 tag 命名空間，因此 tag 一律帶分支前綴（`server-token/v0.2`），本分支只認 `server-token/` 開頭的 tag——不會把 `mcp-oauth` 的版本誤判成自己的更新。

---

## 注意事項

- `PBI_MASK_KEY` 為個人專屬，請勿共用或外洩
- `config/settings.local.json`、`config/pbi_configs.json` 皆含敏感資訊，請勿手動納入版本控制
- Access Token 快取（`config/pbi_configs.json`）刻意放在 Skill 自己的目錄下，而不是使用者工作區的 `.claude/`——後者是您當下開啟的任意程式碼專案，該專案的 `.gitignore` 是否排除 `.claude/` 不在本 Skill 掌控範圍內，含 token 的檔案有被誤 commit 的風險
- Access Token 有效期約 1 小時，過期後重新執行 Skill 即可自動更新
- 語意模型由管理員集中維護；不論模型內容或使用者的已分配模型是否變動，Skill 每日至少強制重新同步一次，不會永遠沿用舊清單
- Python 3.9+ 不足或標準函式庫模組缺失時，Skill 會在最開始就清楚告知原因並停止，不會執行到一半才失敗
