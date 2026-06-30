# ai-slack-bot

Threaded Claude or Codex agent conversations in Slack. One Slack Assistant chat or Slack thread = one task.

Use the native Slack Assistant chat surface for the new setup, or keep using the legacy @mention/thread flow in channels and DMs. Claude and Codex can execute code, search the web, generate images and videos, and send files directly in the conversation.

## Features

- **Assistant chats** — native Slack Assistant conversations with titles, status, suggested prompts, and chat history
- **Threaded conversations** — each Slack Assistant chat or legacy Slack thread is an independent agent session
- **Full agent capabilities** — bash execution, file operations, web search
- **Media support** — Claude can generate and upload images (matplotlib, PIL) and videos (ffmpeg, moviepy)
- **Permission system** — tool use requires approval via Slack buttons (Allow / Deny / Auto-approve)
- **Auto-approve mode** — toggle per-thread to skip permission prompts
- **Conversation summaries** — Claude automatically appends a summary to each response
- **Multiple backends** — Claude Code CLI, Codex CLI, Messages API, or Managed Agents API
- **Per-conversation backend switching** — use Codex by default and switch specific conversations back to Claude

## Quick start

```bash
git clone https://github.com/kevin-thankyou-lin/claude-slack-bot.git
cd claude-slack-bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your Slack tokens (see Slack App Setup below)
# No API key needed with the default codex backend after `codex login`
python -m claude_slack_bot.main
```

> **No Anthropic API key?** The default `codex` backend uses your Codex CLI login. Just make sure `codex` is installed and logged in. Claude Code threads remain available through `backend claude-code` after `claude auth`.

The default configuration enables Slack Assistant chats. To keep only the legacy Slack thread setup, set `ENABLE_SLACK_ASSISTANT=false` in `.env`.

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
   - `assistant:write` — support native Slack Assistant chats
   - `chat:write` — send messages
   - `channels:history` — read channel messages
   - `groups:history` — read private channel messages
   - `im:history` — read DMs
   - `im:read` — access the bot's DM/Assistant conversation surface
   - `im:write` — send messages in the bot's DM/Assistant conversation surface
   - `mpim:history` — read group DMs
   - `files:write` — upload files
   - `files:read` — read file metadata
   - `users:read` — read user info

### 4. Subscribe to Events

1. Go to **Features > Event Subscriptions**
2. Toggle **Enable Events** on
3. Under **Subscribe to bot events**, add:
   - `app_mention` — when someone @mentions the bot
   - `assistant_thread_started` — when a user starts a native Assistant chat
   - `assistant_thread_context_changed` — Assistant context updates
   - `message.channels` — messages in public channels
   - `message.groups` — messages in private channels
   - `message.im` — direct messages
   - `message.mpim` — group direct messages

### 5. Enable the Slack app Chat tab

1. Go to **Features > App Home**
2. Leave **Home Tab** off unless you are adding a custom Block Kit home view
3. Enable **Chat Tab** / **Messages Tab**
4. Enable **Allow users to send Slash commands and messages from the chat tab** or turn off read-only mode for the Messages tab

### 6. Enable Agents & AI Apps

Slack Assistant chats require the workspace's Agents & AI Apps feature.

1. In the Slack app settings, enable the Agents & AI Apps feature if it is available for your workspace
2. If the feature is not available, use the legacy setup below

### 7. Enable Interactivity

1. Go to **Features > Interactivity & Shortcuts**
2. Toggle **Interactivity** on
3. (No request URL needed — Socket Mode handles this)

### 8. Install the App

1. Go to **Settings > Install App**
2. Click **Install to Workspace** and authorize
3. Copy the **Bot User OAuth Token** (`xoxb-...`) — this is your `SLACK_BOT_TOKEN`

### 9. Invite the Bot to Channels

For legacy channel threads, invite the bot to any channel where you want to use it:
```
/invite @Claude Bot
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
SLACK_BOT_TOKEN=xoxb-...          # From step 8
SLACK_APP_TOKEN=xapp-...          # From step 2
ENABLE_SLACK_ASSISTANT=true       # Enables native Slack Assistant chats
# That's it! No API key needed with the default codex backend after `codex login`.
```

Optional settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_BACKEND` | `codex` | `codex`, `claude-code`, `messages` (API), or `managed` (beta) |
| `DEFAULT_MODEL` | `claude-opus-4-7` | Claude model for `claude-code` / Messages |
| `CODEX_MODEL` | `gpt-5.6-sol` | Codex model for `codex` threads |
| `EFFORT` | `high` | Reasoning effort: `low`, `medium`, `high`, `xhigh`, or `max` |
| `CODEX_SERVICE_TIER` | `fast` | Codex service tier; set empty to disable fast mode |
| `CODEX_BIN` | `codex` | Codex CLI executable |
| `CODEX_BYPASS_APPROVALS_AND_SANDBOX` | `true` | Run Codex non-interactively without CLI approval prompts |
| `ENABLE_SLACK_ASSISTANT` | `true` | Register Slack Assistant chat listeners |
| `DB_PATH` | `data/claude_slack_bot.db` | SQLite database path |
| `SUMMARY_INTERVAL_TURNS` | `5` | Post a summary every N turns |
| `CONFIRMATION_TIMEOUT_SECONDS` | `300` | Auto-expire unanswered permission prompts |
| `LOG_LEVEL` | `INFO` | Logging level |

## New Slack Assistant Setup

Slack Assistant chats are the preferred setup when the workspace supports Agents & AI Apps.

1. Import the current `manifest.json`, or manually add the Assistant scopes/events listed above.
2. Reinstall the Slack app after changing scopes or events.
3. Set `ENABLE_SLACK_ASSISTANT=true` in `.env`.
4. Start the bot:

```bash
python -m claude_slack_bot.main
```

5. In Slack, open the bot from the app's Messages/Chat UI or the AI Assistant split-view.
6. Start a new chat and send a task.

When a new Assistant chat starts, the bot posts a ready message, sets suggested prompts, updates the title from the first user prompt, and uses Assistant status text while work is running. Each Assistant chat is persisted as a separate conversation with `surface = "slack_assistant"` in the local SQLite database.

## Legacy Slack Thread Setup

Legacy setup keeps the original Slack behavior and does not require Slack Assistant features.

1. Keep the standard Slack app scopes/events:
   - `app_mentions:read`
   - `chat:write`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `files:write`
   - `files:read`
   - `users:read`
2. Enable Socket Mode and Interactivity.
3. Set this in `.env`:

```bash
ENABLE_SLACK_ASSISTANT=false
```

4. Start the bot:

```bash
python -m claude_slack_bot.main
```

5. In Slack, @mention the bot in a channel or send it a DM. The bot responds in a normal Slack thread, and replies in that thread continue the same session.

You can also leave `ENABLE_SLACK_ASSISTANT=true` and still use legacy channel mentions. Assistant chats and legacy threads run side by side; the database `surface` value keeps their routing separate.

## Migrating From Legacy Threads To Assistant Chats

Existing legacy threads continue to work. To move the app to the new Assistant chat setup:

1. Update the Slack app manifest or manual app settings:
   - add bot scope `assistant:write`;
   - add bot events `assistant_thread_started` and `assistant_thread_context_changed`;
   - enable the app's Chat/Messages tab and allow users to send messages from it;
   - enable the workspace's Agents & AI Apps feature if available.
2. Reinstall the Slack app so the new scopes and events take effect.
3. Update `.env`:

```bash
ENABLE_SLACK_ASSISTANT=true
```

4. Restart the bot and verify startup has no import error for `slack_bolt.middleware.assistant.async_assistant`.
5. Start a fresh Assistant chat from the Slack Assistant/App Messages UI.

The database migrates automatically by adding a `surface` column when needed. Existing records default to `slack_thread`; new Assistant chats are marked `slack_assistant`. If the Assistant feature is blocked by workspace settings or Slack plan availability, set `ENABLE_SLACK_ASSISTANT=false` and keep using the legacy flow.

## Usage

### Start an Assistant chat

Use this for the new setup:

1. Open the bot in Slack's app Messages/Chat UI or the AI Assistant split-view.
2. Click to start a new chat.
3. Send a task, for example:

```text
help me inspect this repo and summarize the current test status
```

The first prompt becomes the chat title, and the conversation appears in the Assistant chat history. Open the same bot/Assistant UI later to see previous chats by title and continue the one you need.

Suggested prompts may include:

```text
cd <project-folder>
backend codex
model gpt-5.6-sol
effort high
```

### Start a legacy Slack thread

@mention the bot in any channel:
```
@Claude Bot help me write a Python script to parse CSV files
```

The bot responds in a Slack thread. All replies in that thread continue the conversation.

### Switch backends

Claude remains available as `claude-code`, and Codex is available as `codex`.

```
backend codex
codex: inspect this repo and fix the failing tests
backend claude-code
claude: continue with the existing Claude path
```

`model <name>`, `effort <level>`, `fast` / `/fast` / `mode fast`, `service-tier <default|fast>`, and `cd <path>` continue to apply to the current thread. Fast mode sets Codex `service_tier` to `fast`. `cd` accepts full paths, folder names under `PROJECTS_DIR`, and slashless mount shorthand such as `cd mnt amlfs-07 shared linke`.

### Permission prompts

When the agent wants to execute code or perform actions, it posts a permission request with three buttons:

- **Allow** — approve this single action
- **Deny** — reject this action
- **Auto-approve all** — approve this and all future actions in this thread

### Media generation

Ask the agent to create visuals:
```
@Claude Bot create a bar chart comparing Python, Rust, and Go performance
```

The agent writes and executes a matplotlib script, then uploads the image to the conversation.

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
  → Response → Slack Assistant chat or Slack thread
```

- **ThreadCoordinator** maps each Slack Assistant chat or legacy Slack thread to an agent session
- **PermissionManager** tracks auto-approve state per thread
- **ClaudeCodeBackend** uses Claude Code CLI sessions
- **CodexCliBackend** uses Codex CLI non-interactive runs
- **MessagesBackend** uses the stable Anthropic Messages API with a local agentic loop
- **ManagedAgentBackend** uses the beta Managed Agents API for stateful server-side sessions
- **SQLite** persists thread mappings, message history, pending confirmations, and the conversation `surface`

## License

MIT
