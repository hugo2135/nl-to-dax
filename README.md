# nl-to-dax

自然語言轉 DAX 查詢的 Claude Code Skill，針對 Power BI REST API 設計。輸入需求描述，自動完成環境初始化、模型同步、關聯驗證、篩選套用，直接呼叫 API 並輸出 CSV 結果。語意模型由申請程式集中管理，首次使用自動同步至本地。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 自動初始化 | 啟動時檢查環境，自動建立設定檔並引導完成申請流程 |
| 多模型支援 | 支援多個 Power BI 資料集，啟動時列出可用模型供選擇 |
| 模型概覽展示 | 取得 Token 後自動彙整模型中的資料表與量值，讓使用者了解可查詢範圍 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 直接執行 | Server 統一處理 Azure AD 驗證，Skill 直接使用 access token 執行查詢並輸出 CSV |

---

## 前置條件

- Python 3.9+（無需額外安裝第三方套件，僅使用標準函式庫）
- Claude Code CLI（已安裝並登入）

---

## 初次設定

### 步驟一：申請帳號並取得金鑰

前往管理員提供的服務網址，完成以下流程：

1. 點選「立即註冊」，填入 Email 與密碼後送出申請
2. 等待管理員開通帳號
3. 開通後登入，進入個人頁面點選「領取 PBI_MASK_KEY」
4. 金鑰只顯示一次，請立即複製並妥善保存

### 步驟二：執行 Skill 完成設定

直接執行 `/nl-to-dax`：

- Skill 會自動建立 `.claude/settings.local.json`（預填 `CREDENTIAL_SERVER_URL`，`PBI_MASK_KEY` 留空）
- 提示您填入 PBI_MASK_KEY（可直接提供給 Claude 代為寫入，或自行編輯檔案）
- 金鑰設定完成後重新執行，Skill 自動同步語意模型並取得 Access Token

> **注意**：金鑰為個人專屬，僅能領取一次；遺失請聯絡管理員重設。

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                        # Skill 主體目錄
│   ├── SKILL.md                      # Skill 執行指令（Claude 讀取）
│   ├── filters/                      # DAX 篩選設定檔
│   │   ├── default_order.json        # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json        # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json      # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       ├── shared/                   # 跨平台共用 Python 腳本
│       │   ├── check_setup.py        # 環境檢查（回傳 JSON 狀態）
│       │   ├── fetch_credential.py   # 向申請程式取得 Access Token
│       │   ├── fetch_model.py        # 向申請程式同步語意模型
│       │   └── pbi_api_client.py     # Power BI REST API 客戶端
│       ├── windows/                  # Windows PowerShell 觸發腳本
│       ├── macos/                    # macOS bash 觸發腳本
│       └── linux/                    # Linux bash 觸發腳本
└── README.md
```

執行期間自動產生（不納入版本控制）：

```
.claude/
└── pbi_configs.json          # Access Token 快取（敏感，受 .gitignore 保護）

pbi_query/
├── models_index.json         # 可用模型清單
├── <pbi_config_id>/
│   ├── relationships.json    # 資料表關聯性
│   └── tables/
│       └── table_<表名>.json # 各資料表結構（含量值定義）
└── query_result.csv          # 查詢結果
```

---

## 使用方式

### 安裝 Skill

將 `nl-to-dax/` 目錄放入 Claude Code 的 Skill 路徑（`.claude/skills/`），使其在對話中可被呼叫。

### 執行 Skill

在 Claude Code 中輸入 `/nl-to-dax`，描述您想查詢的資料需求（中英文皆可）：

```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 自動完成：環境初始化 → 模型選擇 → 模型概覽展示 → DAX 生成 → API 執行 → CSV 輸出。

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

## 輸出結果

每次執行輸出以下三項：

- DAX 查詢語法（程式碼片段）
- 使用到的欄位與量值清單
- `pbi_query/query_result.csv`（查詢結果）及執行摘要（筆數回報）

---

## 注意事項

- `PBI_MASK_KEY` 為個人專屬，請勿共用或外洩
- `.claude/pbi_configs.json` 含 Access Token，受 `.gitignore` 保護，請勿手動納入版本控制
- Access Token 有效期約 1 小時，過期後重新執行 Skill 即可自動更新
- 語意模型由管理員集中維護，版本更新後 Skill 下次啟動時自動偵測並重新同步
