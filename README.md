# nl-to-dax（solo 分支）

自然語言轉 DAX 查詢的 Claude Code Skill，針對 Power BI REST API 設計。輸入需求描述，自動完成環境初始化、關聯驗證、篩選套用，直接呼叫 API 並輸出 CSV 結果。此分支為自用模式：Azure AD 憑證直接設定在本機，不經過任何中央 Server；語意模型結構由您自行透過瀏覽器 F12 擷取後轉換取得。

---

## 分支說明

此 Skill 依「憑證取得方式」維護三條分支，服務不同情境：

| 分支 | 適用情境 | 認證方式 |
|------|----------|----------|
| `solo` | 自用／個人使用，不經過集中管理的 Server | 直接在 Skill 內填寫 Azure AD Tenant ID / Client ID / Client Secret |
| `server-token` | 集團／多人使用，舊方案 | 向 Server 申請 `PBI_MASK_KEY`，換取 Access Token |
| `mcp-oauth` | 集團／多人使用，現行方案 | MCP connector + OAuth，Skill 不接觸任何憑證 |

以下內容說明的是**本分支（`solo`）**的安裝與使用方式。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 自用免 Server | Azure AD 憑證直接設定在本機檔案，不需要申請帳號或金鑰 |
| 多模型支援 | 支援多個 Power BI 資料集，啟動時列出可用模型供選擇 |
| 模型概覽展示 | 取得 Token 後自動彙整模型中的資料表與量值，讓使用者了解可查詢範圍 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 直接執行 | 直接以 Azure AD 服務主體換取 Access Token 並執行查詢、輸出 CSV |
| 查詢書籤 | 查詢成功後可命名存檔，下次執行時列在模型概覽最下方，可直接重跑或用原需求重新生成 |
| 版本提醒 | 每日至多檢查一次是否有新版本，有更新時簡短提醒，不中斷使用 |
| 環境自檢 | 啟動時一次檢查 Python 版本、設定狀態、版本更新與書籤，異常時清楚告知原因 |

---

## 前置條件

- Python 3.9+（無需額外安裝第三方套件，僅使用標準函式庫）
- **Claude Code CLI 或 VS Code + Claude Code 擴充功能**（不支援 Claude 桌面版／Cowork／claude.ai 網頁版：這些介面的 skill 執行環境是每次對話重新產生的暫存沙盒，設定檔無法持續保存）
- Git（版本提醒功能需要，用於查詢遠端最新版號；未安裝或無法連線時會靜默略過，不影響其他功能）
- 一組具備 Power BI API 存取權限的 Azure AD 服務主體（App Registration），且該服務主體已被加入目標 Power BI workspace 的成員

---

## 安裝 Skill

把整個 `nl-to-dax/` 目錄放進 Claude Code 會讀取的 skill 路徑，以下兩種位置都支援：

- **專案內安裝**：`<你的專案>/.claude/skills/nl-to-dax/` — 只在這個專案生效
- **使用者層級安裝**：`~/.claude/skills/nl-to-dax/` — 對所有專案生效

兩種安裝方式行為完全一致，Skill 會自動判斷目前工作的專案目錄，不需要額外設定。

---

## 初次設定

以下兩件事互不依賴，順序不拘，兩者都完成後才能查詢：

### 一、憑證設定

1. 複製 `<SKILL_ROOT>/config/azure_ad_credentials.json.example` 為同目錄下的 `azure_ad_credentials.json`
2. 自行在編輯器中填入 Azure AD 服務主體的 `tenant_id`/`client_id`/`client_secret`（`credentials.default` 底下）
3. 對每個要查詢的模型，在 `models` 底下以該模型的 `dataset_id` 為 key 新增一筆，填入 `dataset_name`（顯示名稱）與 `workspace_id`（可從 Power BI 服務的報表網址或工作區設定取得）

> **`tenant_id`/`client_id`/`client_secret` 屬於敏感憑證，請勿提供給 Claude 讀取或代填**——Claude 不會、也不能用 Read/Edit 工具存取這個檔案，這三個欄位需要您自己填寫。`dataset_id`/`workspace_id`/`dataset_name` 不是機密資訊，Claude 可以在對話中看到並使用。

### 二、取得語意模型結構

這個 Skill 不會、也不能自動連進 Power BI 把模型結構匯出——您需要用瀏覽器開發者工具手動擷取：

1. 用瀏覽器打開該 Power BI 報表頁面，按 **F12** 開啟開發者工具，切換到 **Network（網路）** 分頁
2. 重新整理頁面，或進入「模型檢視／管理關聯」等會載入完整結構的畫面
3. 在 Network 清單中找到回應內容含有 `tables`、`columns`、`measures`、`relationships` 的請求，複製完整 Response 內容
4. 貼到純文字編輯器另存為 UTF-8 編碼的 `.json` 檔（例如 `model.json`）
5. 執行：

   ```
   python "<SKILL_ROOT>/scripts/shared/chunk_model.py" <workspace_root> <dataset_id> model.json [description.txt]
   ```

   `dataset_id` 需與「憑證設定」步驟 3 登記的同一個 dataset_id 一致；`description.txt` 為選填的模型整體說明（純文字檔）。

> 若同時需要一份給非技術讀者看的資料字典，可以另外用 [bi_model_description](https://github.com/hugo2135/bi_model_description) skill 對同一份 `model.json` 產生 `.txt` 說明文件，再把該檔案路徑當作 `chunk_model.py` 的 `description_file` 參數。

完成以上兩件事後，執行 `/nl-to-dax` 即可開始查詢。

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                          # Skill 主體目錄（<SKILL_ROOT>）
│   ├── SKILL.md                        # Skill 執行指令（Claude 讀取）
│   ├── VERSION                         # 目前版號（major.build，例如 0.1）
│   ├── config/
│   │   └── azure_ad_credentials.json.example   # Azure AD 憑證與模型 dataset_name/workspace_id 範本
│   ├── filters/                        # DAX 篩選設定檔
│   │   ├── default_order.json          # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json          # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json        # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       └── shared/                     # 跨平台共用 Python 腳本（由 Claude 直接以 python 呼叫，無 shell wrapper）
│           ├── preflight.py            # 啟動前置檢查：一次回傳 Python 環境／設定狀態／版本更新／查詢書籤
│           ├── skill_settings.py       # 共用工具：skill_root/workspace_root 判斷、憑證檔讀取
│           ├── bookmarks.py            # 查詢書籤的存取（list/show/save/delete）與環境持久性偵測
│           ├── check_setup.py          # 環境檢查（回傳已登記模型的憑證/結構就緒狀態）
│           ├── check_update.py         # 每日版本檢查（比對遠端 git tag）
│           ├── chunk_model.py          # 把 F12 擷取的語意模型 JSON 拆成 relationships/tables，以 dataset_id 命名資料夾
│           ├── fetch_credential.py     # 直接向 Azure AD 換取 Access Token
│           ├── model_overview.py       # 彙整單一模型的 relationships + tables，供模型概覽使用
│           └── pbi_api_client.py       # Power BI REST API 客戶端
└── README.md
```

執行期間自動產生（皆已納入 `.gitignore`）：

```
<SKILL_ROOT>/config/
├── pbi_configs.json              # Access Token 快取（敏感）
├── bookmarks.json                # 查詢書籤（依模型分組）
└── env_probe.json                # 判斷本機檔案能否跨對話存活的探針

<你的工作區根目錄>/
├── pbi_config/                   # 語意模型快取（chunk_model.py 產生，跨查詢重複使用）
│   └── <dataset_id>/
│       ├── relationships.json    # 資料表關聯性
│       ├── description.txt       # 模型整體說明（選填，chunk_model.py 的 description_file 參數提供）
│       └── tables/
│           └── table_<表名>.json # 各資料表結構（含量值定義）
└── pbi_query/                    # 每次查詢的暫存產物（用完即可清除）
    ├── dax_query.txt             # 本次生成的 DAX 查詢
    └── query_result.csv          # 查詢結果
```

---

## 使用方式

在 Claude Code 中輸入 `/nl-to-dax`，描述您想查詢的資料需求（中英文皆可）：

```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 自動完成：環境初始化（Python 檢查）→ 版本檢查 → 模型選擇 → 模型概覽展示 → DAX 生成 → API 執行 → CSV 輸出。

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

之所以保留第二個選項，是因為存下的 DAX 是「凍結」的——如果當初生成的是寫死的日期區間（而非 `TODAY()` 這類相對日期函數），或之後 `filters/` 的篩選規則有調整，直接重跑會得到過時的結果。Skill 偵測到書籤含字面日期時會主動提醒。

書籤存在 `<SKILL_ROOT>/config/bookmarks.json`，依模型的 `dataset_id` 分組，所以不同模型的書籤不會互相混淆。

---

## 輸出結果

每次執行輸出以下三項：

- DAX 查詢語法（程式碼片段）
- 使用到的欄位與量值清單
- `pbi_query/query_result.csv`（查詢結果）及執行摘要（筆數回報）

---

## 版本更新

每次執行時，Skill 每日最多向遠端倉庫查詢一次最新版號（比對 git tag），若偵測到有更新版本會簡短提醒一次，不會中斷查詢流程。要更新到最新版本，請重新取得本倉庫最新內容並覆蓋部署路徑。

---

## 疑難排解

- **Access Token 換取失敗，或執行查詢時回報權限錯誤**：請至 Power BI 管理後台（Tenant settings → Developer settings）確認已開啟「Allow service principals to use Power BI APIs」，這是 Power BI 租戶層級的設定，跟 Azure AD 的 API permissions/consent 是兩回事。
- **服務主體有 Token 但查不到 workspace 內容**：確認該服務主體已被加入目標 workspace 的成員（Member 或以上）。
- **查詢執行失敗，錯誤訊息不明確**：`executeQueries` 這個 REST API 只支援 Premium、Premium Per User (PPU) 或 Fabric 容量的 workspace（底層走 XMLA endpoint）；一般 Pro workspace 會查詢失敗，且錯誤訊息通常不會直接說明是容量問題。
- **原本可用突然失敗，且時間點接近設定憑證滿兩年**：Azure AD Client Secret 最長效期為 24 個月，此 Skill 不做自動輪替，到期需自行在 Azure Portal 重新產生並更新 `azure_ad_credentials.json`。

---

## 注意事項

- `config/azure_ad_credentials.json` 含 Azure AD 憑證（`tenant_id`/`client_id`/`client_secret`），請勿提供給 Claude 讀取或代填，也請勿手動納入版本控制
- Access Token 快取（`config/pbi_configs.json`）刻意放在 Skill 自己的目錄下，而不是使用者工作區的 `.claude/`——後者是您當下開啟的任意程式碼專案，該專案的 `.gitignore` 是否排除 `.claude/` 不在本 Skill 掌控範圍內，含 token 的檔案有被誤 commit 的風險
- Access Token 有效期約 1 小時，過期後重新執行 Skill 即可自動更新
- Python 3.9+ 不足或標準函式庫模組缺失時，Skill 會在最開始就清楚告知原因並停止，不會執行到一半才失敗

---

## Related projects

- [bi_model_description](https://github.com/hugo2135/bi_model_description) — plain-language data-dictionary generation for BI models
