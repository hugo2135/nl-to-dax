# nl-to-dax

自然語言轉 DAX 查詢的 Claude Code Skill，針對 Power BI REST API 設計。輸入需求描述，自動完成環境初始化、關聯驗證、篩選套用，輸出可直接執行的 DAX 查詢，或直接呼叫 API 取得 CSV 結果。語意模型由申請程式集中管理，首次使用自動同步至本地。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 自動初始化 | 啟動時檢查環境，缺少憑證或模型時自動向申請程式拉取 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 直接執行 | 透過 Azure AD 服務主體驗證，直接執行查詢並輸出 CSV |

---

## 前置條件

- Python 3.9+（無需額外安裝第三方套件，僅使用標準函式庫）
- Claude Code CLI（已安裝並登入）

---

## 初次設定（First-time Setup）

第一次執行 `/nl-to-dax` 時，Skill 會自動建立 `.claude/settings.local.json` 並引導完成設定，步驟如下：

1. **取得 PBI_MASK_KEY**：Skill 會提示前往申請程式網址完成註冊，取得個人專屬金鑰
2. **填入金鑰**：可直接將金鑰提供給 Claude（由 Claude 代為寫入），或自行開啟 `.claude/settings.local.json` 填入
3. **重新執行**：Skill 自動完成憑證與語意模型的下載，無需其他手動操作

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                        # Skill 主體目錄
│   ├── SKILL.md                      # Skill 執行指令（Claude 讀取）
│   ├── config/
│   │   ├── pbi_credentials.jwt       # 憑證檔（自動下載，不納入版本控制）
│   │   └── pbi_credentials.jwt.example  # 憑證格式說明
│   ├── filters/                      # DAX 篩選設定檔
│   │   ├── default_order.json        # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json        # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json      # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       ├── shared/                   # 跨平台共用 Python 腳本
│       │   ├── check_setup.py        # 環境檢查（回傳 JSON 布林結果）
│       │   ├── fetch_credential.py   # 向申請程式拉取憑證 JWT
│       │   ├── fetch_model.py        # 向申請程式拉取語意模型 chunks
│       │   └── pbi_api_client.py     # Power BI REST API 客戶端
│       ├── windows/                  # Windows PowerShell 觸發腳本
│       ├── macos/                    # macOS bash 觸發腳本
│       └── linux/                    # Linux bash 觸發腳本
└── README.md
```

執行期間自動產生：
```
pbi_query/
├── relationships.json     # 資料表關聯性
├── tables/
│   └── table_<表名>.json  # 各資料表結構
├── model_version.json     # 語意模型版本記錄
└── query_result.csv       # 模式二的查詢結果
```

---

## 使用方式

### 安裝 Skill

將 `nl-to-dax/` 目錄放入 Claude Code 的 Skill 路徑（`.claude/skills/`），使其在對話中可被呼叫。

### 執行 Skill

在 Claude Code 中輸入 `/nl-to-dax`，Skill 完成環境初始化後會詢問需求。

**DAX 需求**（中英文皆可）：
```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 會自動生成 DAX 查詢、呼叫 Power BI API 並輸出 CSV 結果。

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

- `pbi_credentials.jwt` 包含敏感憑證，已加入 `.gitignore`，請勿手動納入版本控制
- `PBI_MASK_KEY` 為個人專屬，請勿共用或外洩
- 語意模型更新時，Skill 會在下次執行時自動偵測版本差異並重新同步
- 內建日期表（`LocalDateTable_*`、`DateTableTemplate_*`）會自動略過，節省 Token 消耗
