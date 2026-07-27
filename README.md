# nl-to-dax (mcp-oauth branch)

A Claude Skill that turns natural-language requests into DAX queries, built for the Power BI REST API, generating and executing the query through multi-stage reasoning.

## Branches

This skill is maintained across three branches, split by how credentials are obtained, for different deployment scenarios:

| Branch | Use case | Authentication |
|---|---|---|
| `solo` | Personal/self-service use, no centralized Server | Azure AD Tenant ID / Client ID / Client Secret configured directly in the skill |
| `server-token` | Team/org use, current approach | Request a `PBI_MASK_KEY` from the Server, exchanged for an access token |
| `mcp-oauth` | Team/org use, next-generation approach | MCP connector + OAuth — the skill never touches any credential |

The following describes **this branch (`mcp-oauth`)**'s installation and usage. Authentication is MCP connector + OAuth — no key of any kind to apply for or fill in.

---

## Features

| Feature | Description |
|---|---|
| MCP authentication | OAuth authorization completes in Claude's Settings → Connectors; the skill never holds Azure AD secrets |
| Multi-model support | Supports multiple Power BI datasets; lists available models at startup |
| Model overview | Prefers the admin-authored model description (token-efficient); falls back to auto-summarizing tables and measures |
| Smart filter application | Matches request keywords against filter rules and applies them to the DAX query |
| Relationship validation | Automatically validates table relationships; asks the user when there's a gap |
| DAX generation | Emits complete, REST-API-compliant queries (including `EVALUATE`) |
| API execution | Sends queries directly to the Power BI REST API using the MCP-issued access token; the token exists only within a single conversation — never persisted, never carried across conversations |

---

## Requirements

- Claude, in any MCP-connector-capable interface (e.g., Claude Code, Claude Apps)
- The nl-to-dax MCP connector added under Settings → Connectors
- Git (optional; used only for the skill's version-check feature, unrelated to authentication; silently skipped if unavailable or offline)

---

## Installation

1. Place the entire `nl-to-dax/` directory in a path Claude reads for skills (project-level `.claude/skills/nl-to-dax/` or user-level `~/.claude/skills/nl-to-dax/`)
2. Copy `nl-to-dax/config/site_domain.json.example` to `nl-to-dax/config/site_domain.json`, and fill in the `site_domain` field with the credential application server's actual domain (e.g. `nl-to-dax.example.com`, no `https://` prefix)

---

## First-time setup

Type `/nl-to-dax` in a conversation — if the MCP connector isn't connected yet, the skill walks you through it.

**If your AI app supports an OAuth connector UI (e.g., a Settings → Connectors screen, such as Claude Code or Claude Apps):**

1. If you don't have an account on the credential application server yet, register on the site
2. Notify and wait for admin approval
3. Once approved, add the MCP server in Claude:
   - Name: `nl-to-dax_credential-server`
   - URL: `https://{credential-server-domain}/mcp`
   - Wait for the login page that opens automatically, and log in with your credential-server account
4. Re-run `/nl-to-dax` (CLI users: start a new conversation for it to take effect)

**If your AI app doesn't support an OAuth connector UI (no Settings → Connectors screen — you configure MCP servers via a config file instead):**

1. If you don't have an account on the credential application server yet, register on the site
2. Notify and wait for admin approval
3. Once approved, log in at `https://{credential-server-domain}/` and issue an MCP-use token
4. Using that token, build an MCP server config per your AI app's own spec (URL: `https://{credential-server-domain}/mcp`)
5. Re-run `/nl-to-dax`

> **Note**: account approval is only one prerequisite — the admin must also complete Azure AD credential setup and semantic model assignment before login succeeds. If login fails after approval, it isn't a connection-setup issue, it's a backend-configuration matter — please check with the admin.

---

## Directory structure

```
nl-to-dax/
├── nl-to-dax/                    # Skill root directory (<SKILL_ROOT>)
│   ├── SKILL.md                  # Skill instructions (read by Claude)
│   ├── VERSION                   # Current version (major.build, e.g. 0.1)
│   ├── config/
│   │   └── site_domain.json.example  # Credential-server domain template; copy to site_domain.json on install and fill in the actual domain
│   └── scripts/
│       └── shared/
│           ├── check_update.py         # Optional: daily version check (compares remote git tags), unrelated to authentication
│           └── execute_dax_query.py    # Sends the query directly to the Power BI executeQueries API using the MCP-issued access token
└── README.md
```

Generated at runtime (not version controlled):

```
<your current working directory>/
└── pbi_query/
    └── query_result.csv          # Query result
```

> Semantic model structure (`relationships`/`tables`) and query results are both fetched in real time through the MCP connector — nothing is persisted to a local cache file.

---

## Usage

Type `/nl-to-dax` in Claude and describe the data you need (Chinese or English):

```
Example: list monthly order count and total amount by city, sorted by city
```

The skill automatically runs: MCP auth check (`list_models`) → model selection and full structure retrieval (`get_model_detail`) → model overview → DAX generation → access token acquisition (`get_powerbi_token`, cached within the same conversation) → direct query execution against Power BI → results output.

---

## Filter rules

Filter rules automatically apply business-rule filters when generating DAX. They're centrally maintained by admins at `/admin/pbi-configs` on the credential application server, and retrieved through the `filters` field of the `get_model_detail` MCP tool. To add or adjust filter rules, contact an admin — no modification to the skill itself is needed.

---

## Updates

The skill queries the remote repository for the latest version tag at most once a day (comparing git tags); if a newer version is detected, it gives a brief one-time reminder without interrupting the query flow.

---

## Notes

- The skill holds no underlying credentials such as Azure AD secrets; the access token obtained via `get_powerbi_token` exists only within the context of a single conversation, and is never written to a local file or persisted across conversations
- Semantic models and query results are both fetched in real time; there's no local-cache staleness issue when admins change a user's assigned models
- The Server does not execute queries — it only issues access tokens; DAX queries are sent directly to the Power BI REST API by the skill via `execute_dax_query.py`, so concurrent queries from multiple users can't block the Server
