# ai-slack-bot

Threaded Claude or Codex agent conversations in Slack. One thread = one task.

Talk to the agent by @mentioning the bot in any channel. It responds in a thread, and all follow-up messages in that thread continue the same conversation. Claude and Codex can execute code, search the web, generate images and videos, and send files directly in the thread.

## Features

- **Threaded conversations** — each Slack thread is an independent Claude session
- **Full agent capabilities** — bash execution, file operations, web search
- **Media support** — Claude can generate and upload images (matplotlib, PIL) and videos (ffmpeg, moviepy)
- **Permission system** — tool use requires approval via Slack buttons (Allow / Deny / Auto-approve)
- **Auto-approve mode** — toggle per-thread to skip permission prompts
- **Conversation summaries** — Claude automatically appends a summary to each response
- **Multiple backends** — Claude Code CLI, Codex CLI, Messages API, or Managed Agents API
- **Per-thread backend switching** — use Codex by default and switch specific threads back to Claude

## Quick start

```bash
git clone https://github.com/kevin-thankyou-lin/claude-slack-bot.git
cd claude-slack-bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your Slack tokens (see Slack App Setup below)
# No API key needed — uses your Claude Code subscription by default
python -m claude_slack_bot.main
```

> **No Anthropic API key?** The default `codex` backend uses your Codex CLI login. Just make sure `codex` is installed and logged in. Claude threads remain available through `backend claude` after `claude auth`.

## Slack App Setup

### 1. Option A: Create a Slack App from the Manifest

Use this recommended path unless you specifically need to configure the Slack app by hand. The manifest pre-configures the app settings that are otherwise covered in the manual sections below.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From an app manifest**
3. Select your workspace
4. Paste the contents of `manifest.json` from this repo
5. Click **Create** — all scopes, events, and settings are pre-configured
6. Continue with step 2 to generate `SLACK_APP_TOKEN`, then skip directly to step 6 (Install the App) to get `SLACK_BOT_TOKEN`

### Option B: Manual App Setup

Use this fallback only if you cannot import the manifest or want to review every Slack setting yourself.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**
3. Name it (e.g., "Claude Bot") and select your workspace
4. Click **Create App**
5. Continue through steps 2-5 below to configure Socket Mode, scopes, events, and interactivity manually before installing the app in step 6

### 2. Enable Socket Mode

1. Go to **Settings > Socket Mode** in the left sidebar
2. Toggle **Enable Socket Mode** on
3. Create an app-level token:
   - Name: `socket-mode-token`
   - Scope: `connections:write`
   - Click **Generate**
4. Copy the token (`xapp-...`) — this is your `SLACK_APP_TOKEN`

### 3. Configure Bot Token Scopes

1. Go to **Features > OAuth & Permissions**
2. Under **Bot Token Scopes**, add:
   - `app_mentions:read` — detect @mentions
   - `chat:write` — send messages
   - `channels:history` — read channel messages
   - `groups:history` — read private channel messages
   - `im:history` — read DMs
   - `mpim:history` — read group DMs
   - `files:write` — upload files
   - `files:read` — read file metadata
   - `users:read` — read user info

### 4. Subscribe to Events

1. Go to **Features > Event Subscriptions**
2. Toggle **Enable Events** on
3. Under **Subscribe to bot events**, add:
   - `app_mention` — when someone @mentions the bot
   - `message.channels` — messages in public channels
   - `message.groups` — messages in private channels
   - `message.im` — direct messages

### 5. Enable Interactivity

1. Go to **Features > Interactivity & Shortcuts**
2. Toggle **Interactivity** on
3. (No request URL needed — Socket Mode handles this)

### 6. Install the App

1. Go to **Settings > Install App**
2. Click **Install to Workspace** and authorize
3. Copy the **Bot User OAuth Token** (`xoxb-...`) — this is your `SLACK_BOT_TOKEN`

### 7. Invite the Bot to Channels

In Slack, invite the bot to any channel where you want to use it:
```
/invite @Claude Bot
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
SLACK_BOT_TOKEN=xoxb-...          # From step 6
SLACK_APP_TOKEN=xapp-...          # From step 2
# That's it! No API key needed with the default codex backend after `codex login`.
```

Optional settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_BACKEND` | `codex` | `codex`, `claude-code`, `messages` (API), or `managed` (beta) |
| `DEFAULT_MODEL` | `claude-opus-4-7` | Claude model for `claude-code` / Messages |
| `CODEX_MODEL` | `gpt-5.5` | Codex model for `codex` threads |
| `EFFORT` | `xhigh` | Reasoning effort: `low`, `medium`, `high`, `xhigh`, or `max` |
| `CODEX_BIN` | `codex` | Codex CLI executable |
| `CODEX_BYPASS_APPROVALS_AND_SANDBOX` | `true` | Run Codex non-interactively without CLI approval prompts |
| `DB_PATH` | `data/claude_slack_bot.db` | SQLite database path |
| `SUMMARY_INTERVAL_TURNS` | `5` | Post a summary every N turns |
| `CONFIRMATION_TIMEOUT_SECONDS` | `300` | Auto-expire unanswered permission prompts |
| `LOG_LEVEL` | `INFO` | Logging level |

## Usage

### Start a conversation

@mention the bot in any channel:
```
@Claude Bot help me write a Python script to parse CSV files
```

Claude responds in a thread. All replies in that thread continue the conversation.

### Switch backends

Claude remains available as `claude-code`, and Codex is available as `codex`.

```
backend codex
codex: inspect this repo and fix the failing tests
backend claude
claude: continue with the existing Claude path
```

`model <name>`, `effort <level>`, and `cd <path>` continue to apply to the current thread. `cd` accepts full paths, folder names under `PROJECTS_DIR`, and slashless mount shorthand such as `cd mnt amlfs-07 shared linke`.

### Permission prompts

When Claude wants to execute code or perform actions, it posts a permission request with three buttons:

- **Allow** — approve this single action
- **Deny** — reject this action
- **Auto-approve all** — approve this and all future actions in this thread

### Media generation

Ask Claude to create visuals:
```
@Claude Bot create a bar chart comparing Python, Rust, and Go performance
```

Claude writes and executes a matplotlib script, then uploads the image to the thread.

## Development

```bash
pip install -e ".[dev]"

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
pyright src/

# Test
pytest

# Run
python -m claude_slack_bot.main
```

Operational docs:

- [Launching remote experiments](docs/remote-experiments.md)

## Architecture

```
Slack (Socket Mode)
  → Slack Bolt event router
  → ThreadCoordinator (thread_ts ↔ agent session)
  → BackendRouter (Claude Code, Codex CLI, Messages API, or Managed Agents)
  → Response → Slack thread
```

- **ThreadCoordinator** maps each Slack thread to an agent session
- **PermissionManager** tracks auto-approve state per thread
- **ClaudeCodeBackend** uses Claude Code CLI sessions
- **CodexCliBackend** uses Codex CLI non-interactive runs
- **MessagesBackend** uses the stable Anthropic Messages API with a local agentic loop
- **ManagedAgentBackend** uses the beta Managed Agents API for stateful server-side sessions
- **SQLite** persists thread mappings, message history, and pending confirmations

## License

MIT
