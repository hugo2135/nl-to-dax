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
| API execution | Obtains a single-use, short-lived ticket via MCP; the query script redeems it for an access token in its own memory and calls the Power BI REST API directly. The token never enters the conversation, the command line, or disk |
| Query bookmarks | Save a successful query under a name; it's listed at the bottom of the model overview next time, ready to re-run directly or regenerate from the original request |

---

## Requirements

- Claude, in any MCP-connector-capable interface (e.g., Claude Code, Claude Apps)
- The nl-to-dax MCP connector added under Settings → Connectors
- Python 3.9+ (standard library only, no third-party packages). The MCP half of the flow doesn't need it, but query execution and bookmarks do — the skill checks this up front rather than failing at the last step
- Git (optional; used only for the skill's version-check feature, unrelated to authentication; silently skipped if unavailable or offline)
- **If running in Claude Apps**: its code execution sandbox blocks outbound connections to unknown domains by default. Go to Settings → Capabilities → Network egress and allow **both**:
  - `api.powerbi.com` — executing the DAX query
  - your credential server's domain — redeeming the query ticket

  Missing either produces an error like `Tunnel connection failed: 403 Forbidden`. Note the MCP connector itself still works (it doesn't go through the sandbox network), which makes this easy to misdiagnose as a credential problem.

---

## Installation

1. Place the entire `nl-to-dax/` directory in a path Claude reads for skills (project-level `.claude/skills/nl-to-dax/` or user-level `~/.claude/skills/nl-to-dax/`)
2. Copy `nl-to-dax/config/site_domain.json.example` to `nl-to-dax/config/site_domain.json`, and fill in the `site_domain` field with the credential application server's actual domain (e.g. `nl-to-dax.example.com`, no `https://` prefix)
3. *(Optional, enables self-update)* Copy `nl-to-dax/config/update_source.json.example` to `nl-to-dax/config/update_source.json` and fill in `repo_url` — the repository this skill is distributed from (SSH or HTTPS, whichever your local git credentials are set up for). Without it, version checking and self-update are silently skipped.

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
│   │   ├── site_domain.json.example  # Credential-server domain template; copy to site_domain.json on install and fill in the actual domain
│   │   └── update_source.json.example # Source repository for self-update; copy to update_source.json and fill in repo_url
│   └── scripts/
│       └── shared/
│           ├── preflight.py            # Startup pre-check: returns Python env, update status, and bookmarks in one call
│           ├── bookmarks.py            # Query-bookmark storage (list/show/save/delete) and storage-persistence detection
│           ├── check_update.py         # Daily version check (compares remote git tags), unrelated to authentication
│           ├── update_skill.py          # Updates the local skill to a given version; never touches your config or bookmarks
│           └── execute_dax_query.py    # Redeems the one-time ticket for a token in memory, then calls the Power BI executeQueries API
└── README.md
```

Generated at runtime (not version controlled):

```
<SKILL_ROOT>/config/
├── bookmarks.json                # Saved query bookmarks, grouped by model
└── env_probe.json                # Probe used to tell whether local files survive across conversations

<your current working directory>/
└── pbi_query/
    └── query_result.csv          # Query result
```

> Semantic model structure (`relationships`/`tables`) and query results are both fetched in real time through the MCP connector — nothing is cached locally. Bookmarks are the sole exception (see below); they contain only DAX and your original request, never credentials.

---

## Usage

Type `/nl-to-dax` in Claude and describe the data you need (Chinese or English):

```
Example: list monthly order count and total amount by city, sorted by city
```

The skill automatically runs: MCP auth check (`list_models`) → model selection and full structure retrieval (`get_model_detail`) → model overview → DAX generation → one-time ticket (`get_query_ticket`, fetched fresh for every query, never cached) → the script redeems it and queries Power BI directly → results output.

---

## Filter rules

Filter rules automatically apply business-rule filters when generating DAX. They're centrally maintained by admins at `/admin/pbi-configs` on the credential application server, and retrieved through the `filters` field of the `get_model_detail` MCP tool. To add or adjust filter rules, contact an admin — no modification to the skill itself is needed.

If an admin has configured multiple **query modes** for a model, the skill asks which one to use before fetching its structure (via `list_models`' `query_modes` field, passed as `mode_id` to `get_model_detail`). If an admin has configured **column aliases**, the skill translates colloquial terms in your request (e.g. "the north region") into the actual underlying column value before generating DAX.

---

## Query bookmarks

After a query succeeds, the skill offers to save its DAX under a name you choose. On subsequent runs, bookmarks for the selected model are listed at the bottom of the model overview — just name one to re-run it.

Each bookmark stores both the **DAX** and the **original natural-language request**, so reusing it gives you two options:

- **Run the saved DAX** — skips the reasoning steps; fastest and most token-efficient
- **Regenerate from the original request** — re-runs DAX generation, picking up the latest filter rules, query modes, column aliases, and model structure

The second option exists because saved DAX is frozen: if it was generated with a literal date range (rather than a relative function like `TODAY()`), or an admin has since changed the filter rules, re-running it verbatim returns stale results. The skill flags bookmarks containing literal dates when you reuse them.

> **Claude Apps caveat**: bookmarks are stored in `<SKILL_ROOT>/config/bookmarks.json`. In Claude Apps, skills run in a per-conversation sandbox whose files are discarded when the conversation ends, so bookmarks saved there only last for that conversation — the skill detects this and says so when saving. For bookmarks that persist, use Claude Code CLI or the VS Code extension. (Server-side bookmark storage would fix this, but the credential server currently exposes no MCP tool for it.)

---

## Updates

The skill checks the remote repository for a newer version tag at most once a day. When one is found it tells you and offers to update — it never updates on its own, since that would rewrite the skill's own files mid-run.

Accepting runs `update_skill.py`, which shallow-clones the target tag and overwrites only code (`SKILL.md`, `VERSION`, `scripts/`, and `config/*.example`). **Your own files are never touched**: `site_domain.json`, `update_source.json`, `bookmarks.json`, and in fact any non-`.example` `.json` under `config/`. Files are backed up before being overwritten and restored automatically if anything fails, so a failed update can't leave the skill half-broken.

The new version takes effect in your **next** conversation — the current one already has the old instructions loaded.

Requires `repo_url` in `config/update_source.json` (see Installation). Without it, both the check and the update are silently skipped.

---

## Notes

- The skill holds no underlying credentials such as Azure AD secrets. What reaches the conversation is only a single-use ticket (default 300s TTL); the access token itself is redeemed inside `execute_dax_query.py` and never leaves that process
- The token is handed to the query script through a file that the script deletes the moment it reads it (guaranteed even when the query fails), never as a command-line argument — command lines are readable by other processes on the same machine (`wmic process get commandline` on Windows, `/proc/<pid>/cmdline` on Linux) and can end up in shell history. Note this is defense in depth, not a complete fix: the token still passes through the conversation context, which only a server-side one-time-ticket scheme could avoid
- Semantic models and query results are both fetched in real time; there's no local-cache staleness issue when admins change a user's assigned models
- The Server does not execute queries — it only issues tickets; DAX queries are sent directly to the Power BI REST API by the skill via `execute_dax_query.py`, so concurrent queries from multiple users can't block the Server
