# nl-to-dax

A Claude Code Skill that turns natural-language requests into DAX queries, built for the Power BI REST API. Describe what you need and the skill handles environment setup, model sync, relationship validation, and filter application, then calls the API directly and writes the result to CSV. Semantic models are centrally managed by the credential application server and synced locally on first use.

---

## Branches

This skill is maintained across three branches, split by how credentials are obtained, for different deployment scenarios:

| Branch | Use case | Authentication |
|---|---|---|
| `solo` | Personal/self-service use, no centralized Server | Azure AD Tenant ID / Client ID / Client Secret configured directly in the skill |
| `server-token` | Team/org use, previous approach | Request a `PBI_MASK_KEY` from the Server, exchanged for an access token |
| `mcp-oauth` | Team/org use, current approach | MCP connector + OAuth — the skill never touches any credential |

This document describes **this branch's actual functionality** (the `server-token`-style flow: request a `PBI_MASK_KEY`, exchange it for an access token).

---

## Features

| Feature | Description |
|---|---|
| Automatic bootstrap | Checks the environment at startup, creates a config file (server URL pre-filled), and walks the user through requesting a key |
| Multi-model support | Supports multiple Power BI datasets; lists available models at startup |
| Model overview | Once a token is obtained, automatically summarizes the model's tables and measures so the user knows what's queryable |
| Smart filter application | Matches request keywords against filter config files and applies them to the DAX query |
| Relationship validation | Automatically validates table relationships; asks the user when there's a gap |
| DAX generation | Emits complete, REST-API-compliant queries (including `EVALUATE`) |
| Direct API execution | The Server handles Azure AD auth centrally; the skill uses the access token directly to execute the query and output a CSV |
| Update reminder | Checks for a new version at most once a day; reminds briefly without interrupting the query |
| Environment self-check | Confirms the Python version and required standard-library modules before running; reports the reason clearly on failure |
| Daily model resync | If an admin changes a user's assigned models, the skill resyncs automatically no later than the next day — never stuck on a stale list |

---

## Requirements

- Python 3.9+ (no third-party packages required, standard library only)
- **Claude Code CLI, or VS Code + the Claude Code extension** (Claude Desktop / Cowork / claude.ai web are not supported: those interfaces run skills in a per-conversation ephemeral sandbox, so config files can't persist and `PBI_MASK_KEY` would need to be re-entered every time)
- Git (needed only for the update-reminder feature, to query the latest remote version tag; silently skipped if unavailable or offline)

---

## Installing the skill

Place the entire `nl-to-dax/` directory in a path Claude Code reads for skills — either location works:

- **Project-level install**: `<your-project>/.claude/skills/nl-to-dax/` — active only in this project
- **User-level install**: `~/.claude/skills/nl-to-dax/` — active across all projects

Both installation methods behave identically; the skill auto-detects the current working project, no extra configuration needed.

---

## First-time setup

### Step 1: run the skill to trigger auto-bootstrap

Type `/nl-to-dax` in Claude Code:

- The skill creates `<SKILL_ROOT>/config/settings.local.json` (`CREDENTIAL_SERVER_URL` pre-filled with this repository's configured server URL; `PBI_MASK_KEY` left blank)
- You'll be prompted to complete registration at the server URL to obtain your personal `PBI_MASK_KEY`

### Step 2: register an account and obtain a key

1. Click "Register now", fill in email and password, and submit
2. Wait for admin approval
3. Once approved, log in, go to your profile page, and click "Get PBI_MASK_KEY"
4. The key is shown only once — copy and store it immediately

### Step 3: fill in the key and re-run

Once you have the key, you can hand it to Claude to write into the config file, or edit `settings.local.json` yourself and fill in `PBI_MASK_KEY`. Then re-run `/nl-to-dax` — the skill will automatically sync the semantic model and obtain an access token.

> **Note**: the key is personal and can only be issued once; contact an admin to reset it if lost.

---

## Directory structure

```
nl-to-dax/
├── nl-to-dax/                          # Skill root directory (<SKILL_ROOT>)
│   ├── SKILL.md                        # Skill instructions (read by Claude)
│   ├── VERSION                         # Current version (major.build, e.g. 0.1)
│   ├── config/
│   │   └── default_credential_server_url.txt   # Configurate MCP server URL
│   ├── filters/                        # DAX filter config files
│   │   ├── default_order.json          # Default order filter (always active)
│   │   ├── investigation.json          # Investigation mode (overrides the default filter)
│   │   └── refund_analysis.json        # Refund analysis mode (overrides the default filter)
│   └── scripts/
│       ├── shared/                     # Cross-platform shared Python scripts
│       │   ├── skill_settings.py       # Shared utility: skill_root/workspace_root resolution, config read/write
│       │   ├── check_python_env.py     # Checks Python version and required standard-library modules
│       │   ├── check_setup.py          # Environment check (returns JSON status, including the daily model-sync flag)
│       │   ├── check_update.py         # Daily version check (compares remote git tags)
│       │   ├── fetch_credential.py     # Obtains an access token from the credential application server
│       │   ├── fetch_model.py          # Syncs the semantic model from the credential application server, clears revoked stale cache
│       │   ├── model_overview.py       # Summarizes a single model's relationships + tables for the model overview
│       │   └── pbi_api_client.py       # Power BI REST API client
│       ├── windows/                    # Windows PowerShell trigger scripts
│       ├── macos/                      # macOS bash trigger scripts
│       └── linux/                      # Linux bash trigger scripts
└── README.md
```

Generated at runtime (not version controlled):

```
<your workspace root>/
├── .claude/
│   └── pbi_configs.json          # Access token cache (sensitive, must be protected by .gitignore)
├── pbi_config/                   # Semantic model cache (synced by fetch_model.py, reused across queries)
│   ├── models_index.json         # List of available models
│   ├── last_sync.json            # Date of last successful sync, decides whether a daily resync is needed
│   └── <pbi_config_id>/
│       ├── relationships.json    # Table relationships
│       └── tables/
│           └── table_<name>.json # Each table's structure (including measure definitions)
└── pbi_query/                    # Per-query scratch artifacts (safe to clear after use)
    ├── dax_query.txt             # The DAX query generated for this run
    └── query_result.csv          # Query result
```

> `pbi_config/` holds the model-structure cache; `pbi_query/` holds only a single query's input/output — the two have separate responsibilities.

---

## Usage

Type `/nl-to-dax` in Claude Code and describe the data you need (Chinese or English):

```
Example: list monthly order count and total amount by city, sorted by city
```

The skill automatically runs: environment init (Python check) → version check → model list sync (at most once a day) → model selection → model overview → DAX generation → API execution → CSV output.

---

## Filter config files

Filter config files (`filters/*.json`) automatically apply business-rule filters when generating DAX.

| Config file | Always active | Trigger keywords | Description |
|---|---|---|---|
| `default_order.json` | Yes | — | Excludes non-sales orders such as warehouse transfers, refunds, and cancellations |
| `investigation.json` | No | investigation, debug, anomaly… | Overrides the default filter, shows full data |
| `refund_analysis.json` | No | refund… | Overrides the default filter, shows only refund-related orders |

Adding a filter config file only requires adding a new JSON file in the correct format to the `filters/` folder — the skill loads it automatically on the next run.

---

## Output

Each run outputs:

- The DAX query (code snippet)
- The list of columns and measures used
- `pbi_query/query_result.csv` (query result) and an execution summary (row count)

---

## Updates

On each run, the skill queries the remote repository for the latest version tag at most once a day (comparing git tags); if a newer version is detected, it gives a brief one-time reminder without interrupting the query flow. To update, pull this repository's latest content and overwrite the deployment path.

---

## Notes

- `PBI_MASK_KEY` is personal — do not share or leak it
- `config/settings.local.json` and `.claude/pbi_configs.json` both contain sensitive information — do not add them to version control manually
- Access tokens are valid for about 1 hour; re-running the skill after expiry refreshes it automatically
- Semantic models are centrally maintained by admins; regardless of whether the model content or the user's assigned models changed, the skill forces at least one resync per day — it never keeps running on a stale list forever
- If Python 3.9+ or a required standard-library module is missing, the skill reports the reason clearly at the very start and stops, rather than failing partway through
