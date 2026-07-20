# nl-to-dax（mcp-oauth 分支）

自然語言轉 DAX 查詢的 Claude Skill，針對 Power BI REST API 設計。輸入需求描述，自動完成認證檢查、模型選擇、關聯驗證、篩選套用，透過 nl-to-dax MCP connector 執行查詢、輸出結果。

> **本分支開發中**：認證方式由本機 `PBI_MASK_KEY` 檔案改為 MCP connector + OAuth。`SKILL.md` 呼叫的 MCP 工具（`list_models`、`get_model_detail`、`get_powerbi_token`）schema 已由後端定案；查詢執行不是 MCP 工具，是 Skill 用 `get_powerbi_token` 取得的 Access Token 直接對 Power BI REST API 發送請求（見下方架構說明）。開放問題請見 `CLAUDE.md` 的「開發計畫」章節。

---

## 功能概覽

| 功能 | 說明 |
|------|------|
| MCP 認證 | 透過 Claude 的 Settings → Connectors 完成 OAuth 授權，Skill 不持有 Azure AD 密鑰 |
| 多模型支援 | 支援多個 Power BI 資料集，啟動時列出可用模型供選擇 |
| 模型概覽展示 | 優先使用管理員預先撰寫的模型說明（省 token）；沒有則自動彙整資料表與量值 |
| 智慧篩選套用 | 依據需求關鍵字自動比對篩選設定檔，套用至 DAX 查詢 |
| 關聯驗證 | 自動驗證資料表間的關聯有效性，缺口時主動發問 |
| DAX 生成 | 輸出符合 Power BI REST API 規格的完整查詢語法（含 `EVALUATE`） |
| API 執行 | 用 MCP 取得的 Access Token，直接對 Power BI REST API 發送查詢；Token 僅存在單次對話中，不落地、不跨對話持久化 |

---

## 前置條件

- Claude（支援 MCP connector 的介面，例如 Claude Code、Claude Apps）
- 已連接 nl-to-dax 的 MCP connector（Settings → Connectors）
- Git（僅供選用的 Skill 版本檢查功能使用；未安裝或無法連線時會靜默略過，不影響主要功能）

---

## 安裝 Skill

把整個 `nl-to-dax/` 目錄放進 Claude 會讀取的 skill 路徑（專案內的 `.claude/skills/nl-to-dax/` 或使用者層級的 `~/.claude/skills/nl-to-dax/`）。

---

## 初次設定

在對話中輸入 `/nl-to-dax`：

- 若尚未連接 MCP connector，Skill 會提示：「請至 Settings → Connectors，新增並連線 nl-to-dax connector，完成帳號登入與 OAuth 授權後，重新執行 `/nl-to-dax`。」
- 完成授權後重新執行 `/nl-to-dax`，Skill 會自動取得可用模型清單，不需要另外申請或填寫任何金鑰。

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                    # Skill 主體目錄（<SKILL_ROOT>）
│   ├── SKILL.md                  # Skill 執行指令（Claude 讀取）
│   ├── VERSION                   # 目前版號（major.build，例如 0.1）
│   ├── filters/                  # DAX 篩選設定檔
│   │   ├── default_order.json    # 預設訂單篩選（常態啟用）
│   │   ├── investigation.json    # 排查模式（覆蓋預設篩選）
│   │   └── refund_analysis.json  # 退費分析模式（覆蓋預設篩選）
│   └── scripts/
│       └── shared/
│           ├── check_update.py         # 選用：每日版本檢查（比對遠端 git tag），與認證機制無關
│           └── execute_dax_query.py    # 用 MCP 取得的 Access Token，直接對 Power BI executeQueries API 送查詢
└── README.md
```

執行期間可能自動產生（不納入版本控制）：

```
<使用者目前工作目錄>/
└── pbi_query/
    └── query_result.csv          # 查詢結果（是否保留此落地行為為開放問題，見 CLAUDE.md）
```

> 語意模型結構（`relationships`/`tables`）與查詢結果皆透過 MCP connector 即時取得，不落地為本機快取檔案。

---

## 使用方式

在 Claude 中輸入 `/nl-to-dax`，描述您想查詢的資料需求（中英文皆可）：

```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 自動完成：MCP 認證檢查（`list_models`）→ 模型選擇與取得完整結構（`get_model_detail`）→ 模型概覽展示 → DAX 生成 → 取得 Access Token（`get_powerbi_token`，同一對話內快取複用）→ 直接對 Power BI 執行查詢 → 輸出結果。

---

## 篩選設定檔

篩選設定檔（`filters/*.json`）用於在生成 DAX 時自動套用業務規則篩選條件，與認證方式無關，三條分支（`solo`/`server-token`/`mcp-oauth`）共用同一套邏輯。

| 設定檔 | 常態啟用 | 觸發關鍵字 | 說明 |
|--------|----------|------------|------|
| `default_order.json` | 是 | — | 排除倉庫調撥、退費、取消等非銷售訂單 |
| `investigation.json` | 否 | 排查、調查、異常、debug… | 覆蓋預設篩選，顯示完整資料 |
| `refund_analysis.json` | 否 | 退費、退款、refund… | 覆蓋預設篩選，僅顯示退費相關訂單 |

新增篩選設定檔只需在 `filters/` 資料夾中新增符合格式的 JSON 檔，Skill 會在下次執行時自動載入。

---

## 版本更新

若保留 `check_update.py`（見 CLAUDE.md 開放問題），Skill 每日最多向遠端倉庫查詢一次最新版號（比對 git tag），若偵測到有更新版本會簡短提醒一次，不會中斷查詢流程。

---

## 注意事項

- Skill 不持有 Azure AD 密鑰等底層憑證；查詢用的 Access Token 由 `get_powerbi_token` 取得後僅存在單次對話的上下文中，絕不寫入本機檔案跨對話持久化
- 語意模型與查詢結果皆為即時取得，管理員異動使用者的已分配模型時不會有本機快取過期的問題
- Server 端不執行查詢，只換發 Access Token；DAX 查詢由 Skill 用 `execute_dax_query.py` 直接對 Power BI REST API 發送請求，避免多使用者併發查詢卡住 Server
- `list_models`/`get_model_detail`/`get_powerbi_token` 的 schema 已由後端定案，尚待對照真實部署的 MCP server 進行串接測試（見 CLAUDE.md 開發計畫）
