# nl-to-dax（mcp-oauth 分支）

自然語言轉 DAX 查詢的 Claude Skill，針對 Power BI REST API 設計，透過多階段推理生成並執行 DAX 查詢。

## 分支說明

此 Skill 依「憑證取得方式」維護三條分支，服務不同情境：

| 分支 | 適用情境 | 認證方式 |
|------|----------|----------|
| `solo` | 自用／個人使用，不經過集中管理的 Server | 直接在 Skill 內填寫 Azure AD Tenant ID / Client ID / Client Secret |
| `server-token` | 集團／多人使用，現行方案 | 向 Server 申請 `PBI_MASK_KEY`，換取 Access Token |
| `mcp-oauth` | 集團／多人使用，下一代方案 | MCP connector + OAuth，Skill 不接觸任何憑證 |

以下內容說明**本分支（`mcp-oauth`）**的安裝與使用方式。認證採 MCP connector + OAuth，不需要另外申請或填寫任何金鑰。

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
| API 執行 | 透過 MCP 取得一次性短效 ticket，由查詢腳本自行兌換成 Access Token 後直接對 Power BI REST API 發送查詢；Token 不進對話、不進命令列、不落地 |
| 查詢書籤 | 查詢成功後可命名存檔，下次執行時列在模型概覽最下方，可直接重跑或用原需求重新生成 |

---

## 前置條件

- Claude（支援 MCP connector 的介面，例如 Claude Code、Claude Apps）
- 已連接 nl-to-dax 的 MCP connector（Settings → Connectors）
- Python 3.9+（僅使用標準函式庫，無需安裝第三方套件）。流程中走 MCP 的部分不需要 Python，但執行查詢與書籤功能需要——Skill 會在最開始就檢查，而不是等到最後一步才失敗
- Git（僅供選用的 Skill 版本檢查功能使用；未安裝或無法連線時會靜默略過，不影響主要功能）
- **若在 Claude Apps 中執行**：其 code execution 沙盒預設會擋未知網域的對外連線，需自行到 Settings → Capabilities → Network egress **同時**加入兩個網域：`api.powerbi.com`（執行 DAX 查詢）與申請程式網域（兌換 ticket）。少放行任一個都會收到類似 `Tunnel connection failed: 403 Forbidden` 的錯誤；MCP connector 本身仍會正常運作（不走沙盒網路），因此很容易誤判成憑證問題

---

## 安裝 Skill

1. 把整個 `nl-to-dax/` 目錄放進 Claude 會讀取的 skill 路徑（專案內的 `.claude/skills/nl-to-dax/` 或使用者層級的 `~/.claude/skills/nl-to-dax/`）
2. 複製 `nl-to-dax/config/site_domain.json.example` 為 `nl-to-dax/config/site_domain.json`，將 `site_domain` 欄位填入申請程式（PBI Credential Server）的實際網域（例如 `nl-to-dax.example.com`，不含 `https://` 前綴）
3. *（選用，啟用自動更新）* 複製 `nl-to-dax/config/update_source.json.example` 為 `nl-to-dax/config/update_source.json`，填入 `repo_url`——也就是這份 skill 的發佈倉庫（SSH 或 HTTPS 皆可，看你本機 git 憑證怎麼設定）。沒設定的話，版本檢查與自動更新都會靜默略過。

   更新程式會自動判斷 skill 在倉庫裡的位置：倉庫本身就是 skill（根目錄直接是 `SKILL.md`）或放在任意名稱的子目錄底下都能認得。只有要覆蓋這個判斷時才需要加 `"skill_subdirectory"`——倉庫本身就是 skill 時填空字串 `""`，否則填實際的資料夾名稱。

---

## 初次設定

在對話中輸入 `/nl-to-dax`，若尚未連接 MCP connector，Skill 會引導完成。

**若您使用的 AI App 支援 OAuth 連線介面（例如 Settings → Connectors，如 Claude Code、Claude Apps）：**

1. 若還沒有申請程式的帳號，前往網站完成註冊
2. 通知並等待管理員開通帳號
3. 帳號開通後，於 Claude 新增 MCP Server：
   - 名稱：`nl-to-dax_credential-server`
   - URL：`https://{申請程式網域}/mcp`
   - 等待自動開啟的登入頁面，用申請程式帳密登入
4. 重新執行 `/nl-to-dax`（使用 CLI 需重開對話才會生效）

**若您使用的 AI App 不支援 OAuth 連線介面（沒有 Settings → Connectors 這類介面，需自行寫設定檔連接 MCP Server）：**

1. 若還沒有申請程式的帳號，前往網站完成註冊
2. 通知並等待管理員開通帳號
3. 帳號開通後，登入 `https://{申請程式網域}/`，新增一組 MCP 用 token
4. 依您使用的 AI App 規範，用此 token 建立 MCP Server 設定（URL：`https://{申請程式網域}/mcp`）
5. 重新執行 `/nl-to-dax`

> **注意**：帳號開通只是前置條件之一，管理員也需要完成 Azure AD 憑證設定與語意模型指派，登入畫面才會成功——這不是連線設定的問題，是後端尚未設定完成，請聯繫管理員確認。

---

## 目錄結構

```
nl-to-dax/
├── nl-to-dax/                    # Skill 主體目錄（<SKILL_ROOT>）
│   ├── SKILL.md                  # Skill 執行指令（Claude 讀取）
│   ├── VERSION                   # 目前版號（major.build，例如 0.1）
│   ├── config/
│   │   ├── site_domain.json.example  # 申請程式網域範本，安裝時複製為 site_domain.json 並填入實際網域
│   │   └── update_source.json.example # 自動更新的來源倉庫，複製為 update_source.json 並填入 repo_url
│   └── scripts/
│       └── shared/
│           ├── preflight.py            # 啟動前置檢查：一次回傳 Python 環境／版本更新／查詢書籤
│           ├── bookmarks.py            # 查詢書籤的存取（list/show/save/delete）與環境持久性偵測
│           ├── check_update.py         # 每日版本檢查（比對遠端 git tag），與認證機制無關
│           ├── update_skill.py          # 把本機 skill 更新到指定版本；不會動到你的設定與書籤
│           └── execute_dax_query.py    # 在記憶體中把一次性 ticket 兌換成 Token，再對 Power BI executeQueries API 送查詢
└── README.md
```

執行期間可能自動產生（不納入版本控制）：

```
<SKILL_ROOT>/config/
├── bookmarks.json                # 查詢書籤（依模型分組）
└── env_probe.json                # 判斷本機檔案能否跨對話存活的探針

<使用者目前工作目錄>/
└── pbi_query/
    └── query_result.csv          # 查詢結果
```

> 語意模型結構（`relationships`/`tables`）與查詢結果皆透過 MCP connector 即時取得，不落地為本機快取檔案。書籤是唯一的例外（見下方章節），內容只有 DAX 與需求文字，不含任何憑證。

---

## 使用方式

在 Claude 中輸入 `/nl-to-dax`，描述您想查詢的資料需求（中英文皆可）：

```
範例：列出各縣市的本月訂單數量與總金額，依縣市排序
```

Skill 自動完成：MCP 認證檢查（`list_models`）→ 模型選擇與取得完整結構（`get_model_detail`）→ 模型概覽展示 → DAX 生成 → 取得一次性 ticket（`get_query_ticket`，每次查詢都重新取得、不快取）→ 腳本自行兌換並直接對 Power BI 執行查詢 → 輸出結果。

---

## 篩選設定檔

篩選規則用於在生成 DAX 時自動套用業務規則篩選條件，由管理員於申請程式的 `/admin/pbi-configs` 集中維護，透過 `get_model_detail` 這支 MCP 工具的 `filters` 欄位取得。新增或調整篩選規則請洽管理員，不需要修改 Skill 本身。

若管理員為某個模型設定了多個**查詢模式**，Skill 會在取得完整結構前先詢問要用哪一個（`list_models` 回傳的 `query_modes` 欄位，選定後以 `mode_id` 帶入 `get_model_detail`）。若管理員設定了**欄位別名**，Skill 會在生成 DAX 前，把需求中的口語用詞（例如「北部」）轉換成實際的欄位值。

---

## 查詢書籤

查詢成功後，Skill 會問您要不要把這次的 DAX 存成書籤並命名。之後每次執行 `/nl-to-dax`，選定模型後的模型概覽最下方就會列出該模型已存的書籤，可以直接說名稱重跑。

書籤會同時存下 **DAX** 與**當初的自然語言需求**，重用時提供兩個選項：

- **直接執行**：跳過推理步驟，最快、最省 token
- **用原需求重新生成**：重新走一次 DAX 生成流程，會套用管理員最新的篩選規則、查詢模式、欄位別名與語意模型

之所以保留第二個選項，是因為存下的 DAX 是「凍結」的——如果當初生成的是寫死的日期區間（而非 `TODAY()` 這類相對日期函數），或管理員之後調整過篩選規則，直接重跑會得到過時的結果。Skill 偵測到書籤含字面日期時會主動提醒。

> **Claude Apps 注意事項**：書籤存在 `<SKILL_ROOT>/config/bookmarks.json`。Claude Apps 的 skill 執行環境是每個對話一個沙盒，對話結束後檔案會被清除，因此在該環境存下的書籤只在當次對話有效——Skill 會偵測環境並在儲存時明確告知。若需要長期保存書籤，請改用 Claude Code CLI 或 VS Code 擴充功能。（Server 端書籤儲存才是根本解法，但申請程式目前尚未提供對應的 MCP 工具。）

---

## 版本更新

Skill 每日最多向遠端倉庫查詢一次最新版號（比對 git tag）。偵測到新版本時會告知並**詢問是否要更新**——不會自作主張直接更新，因為那等於在 skill 執行到一半改寫它自己的檔案。

同意後會執行 `update_skill.py`：淺層 clone 目標 tag，只覆蓋程式碼（`SKILL.md`、`VERSION`、`scripts/`、以及 `config/*.example`）。`scripts/` 與 `filters/` 採完整鏡像——上游刪掉的檔案本機也會刪掉，避免歷次改版的殘骸一直累積。**你自己的檔案一律不動**：`site_domain.json`、`update_source.json`、`bookmarks.json`，實際上 `config/` 底下任何非 `.example` 的 `.json` 都受保護。覆蓋或刪除前都會先備份，過程中任一步失敗就整批還原，不會讓 skill 停在「更新到一半」的壞掉狀態。

新版本要**下次對話**才會生效——目前這次對話已經載入舊版指令。

需要在 `config/update_source.json` 填好 `repo_url`（見「安裝 Skill」）。沒設定的話，檢查與更新都會靜默略過。

---

## 注意事項

- Skill 不持有 Azure AD 密鑰等底層憑證。進入對話上下文的只有一次性 ticket（預設 300 秒效期）；真正的 Access Token 由 `execute_dax_query.py` 自行兌換，全程只存在該行程的記憶體中
- 傳給查詢腳本的是 ticket 而不是 token。ticket 單次使用、預設 300 秒失效，就算出現在命令列或對話紀錄裡也幾乎沒有利用價值；真正的 Access Token 從兌換到使用都只在腳本行程內，不寫檔、不進命令列
- 語意模型與查詢結果皆為即時取得，管理員異動使用者的已分配模型時不會有本機快取過期的問題
- Server 端不執行查詢，只發一次性 ticket；DAX 查詢由 Skill 用 `execute_dax_query.py` 直接對 Power BI REST API 發送請求，避免多使用者併發查詢卡住 Server
