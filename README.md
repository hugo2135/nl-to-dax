# nl-to-dax

自然語言轉 DAX 查詢的 Claude Code Skill，針對 Power BI REST API 設計。輸入需求描述與語意模型描述檔，自動完成模型拆分、關聯驗證、篩選套用，輸出可直接執行的 DAX 查詢，或直接呼叫 API 取得 CSV 結果。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| 語意模型拆分 | 將大型 Power BI JSON 描述檔切分為輕量化的表結構與關聯性檔案 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 直接執行 | 透過 Azure AD 服務主體驗證，直接執行查詢並輸出 CSV |

---

## 前置條件

- Python 3.9+（無需額外安裝第三方套件，僅使用標準函式庫）
- Claude Code CLI（已安裝並登入）
- 使用模式二時，額外需要：
  - `pbi_credentials.jwt`（向供應方申請）
  - 環境變數 `PBI_MASK_KEY`（向供應方取得）

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                        # Skill 主體目錄
│   ├── SKILL.md                      # Skill 執行指令（Claude 讀取）
│   ├── config/
│   │   ├── pbi_credentials.jwt       # 憑證檔（不納入版本控制）
│   │   └── pbi_credentials.jwt.example  # 憑證格式說明
│   ├── filters/                      # DAX 篩選設定檔
│   │   ├── default_order.json        # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json        # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json      # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       ├── shared/                   # 跨平台共用 Python 腳本
│       │   ├── chunk_model.py        # 語意模型拆分器
│       │   └── pbi_api_client.py     # Power BI REST API 客戶端
│       ├── windows/                  # Windows PowerShell 觸發腳本
│       ├── macos/                    # macOS bash 觸發腳本
│       └── linux/                    # Linux bash 觸發腳本
└── README.md
```

---

## 使用方式

### 安裝 Skill

將 `nl-to-dax/` 目錄放入 Claude Code 的 Skill 路徑（`.claude/skills/`），使其在對話中可被呼叫。

### 執行 Skill

在 Claude Code 中輸入 `/nl-to-dax` 並提供以下三個輸入：

1. **執行模式**
   - 模式一：僅輸出 DAX 查詢語法（不呼叫 API）
   - 模式二：生成並直接執行查詢，輸出 CSV 結果

2. **DAX 需求**（中英文皆可）
   ```
   範例：列出各縣市的本月訂單數量與總金額，依縣市排序
   ```

3. **語意模型描述檔路徑**
   ```
   範例：C:\Users\user\Documents\semantic_model.json
   ```

### 設定憑證（模式二專用）

```powershell
# Windows PowerShell
$env:PBI_MASK_KEY = "your-secret-key"
```

```bash
# macOS / Linux
export PBI_MASK_KEY="your-secret-key"
```

將供應方提供的 `pbi_credentials.jwt` 放至：

```
nl-to-dax/config/pbi_credentials.jwt
```

---

## 篩選設定檔

篩選設定檔（`filters/*.json`）是本 Skill 的核心機制之一，用於在生成 DAX 時自動套用業務規則篩選條件。

| 設定檔 | 常態啟用 | 觸發關鍵字 | 說明 |
|--------|----------|------------|------|
| `default_order.json` | 是 | — | 排除倉庫調撥、退費、取消等非銷售訂單 |
| `investigation.json` | 否 | 排查、調查、異常、debug… | 覆蓋預設篩選，顯示完整資料 |
| `refund_analysis.json` | 否 | 退費、退款、refund… | 覆蓋預設篩選，僅顯示退費相關訂單 |

新增篩選設定檔只需在 `filters/` 資料夾中新增符合格式的 JSON 檔，Skill 會在下次執行時自動載入。

---

## 輸入格式說明

語意模型描述檔支援兩種格式：

- **原始 Power BI 格式**：包含 `clientDataModel.dataModel` 結構，關聯使用 `fromTableRef/toTableRef`
- **簡化語意模型格式**：`tables` 與 `relationships` 直接位於根層

`chunk_model.py` 會自動偵測並處理兩種格式。

---

## 輸出結果

**模式一**輸出：
- DAX 查詢語法（程式碼片段）
- 使用到的欄位與量值清單

**模式二**額外輸出：
- `pbi_query/query_result.csv`（查詢結果）
- 執行摘要（筆數回報）

---

## 注意事項

- `pbi_credentials.jwt` 包含敏感憑證，已加入 `.gitignore`（透過 `.claude` 目錄層級排除），請勿手動納入版本控制
- Skill 執行時會自動清除上一次的 `pbi_query/` 資料，確保結果不殘留
- 內建日期表（`LocalDateTable_*`、`DateTableTemplate_*`）會自動略過，節省 Token 消耗
