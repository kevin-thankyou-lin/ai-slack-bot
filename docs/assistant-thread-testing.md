# Assistant Thread Testing Guide

## Local Branch

```bash
cd /home/amandlekar/installed_libraries/pretraining/claude-slack-bot-assistant-threads
git status --short --branch
```

Expected branch:

```text
feature/assistant-thread-conversations
```

## Slack App Setup

In Slack App settings:

1. Enable the Agents & AI Apps feature.
2. Add bot scopes:
   - `assistant:write`
   - `chat:write`
   - `im:history`
   - existing bot scopes from `manifest.json`
3. Subscribe to bot events:
   - `assistant_thread_started`
   - `assistant_thread_context_changed`
   - `message.im`
   - existing bot events from `manifest.json`
4. Reinstall the Slack app after changing scopes/events.

The updated local `manifest.json` includes the new Assistant scope/events.

## Local Config

The copied `.env` should already contain the Slack tokens from the original
repo. Confirm this setting is enabled or absent:

```bash
ENABLE_SLACK_ASSISTANT=true
```

If you need to fall back to legacy thread behavior:

```bash
ENABLE_SLACK_ASSISTANT=false
```

## Start The Bot

Use the same command you normally use for this repo. Common local options:

```bash
python -m claude_slack_bot.main
```

or, if running from an editable install/venv:

```bash
claude-slack-bot
```

Expected startup signs:

- no import error for `slack_bolt.middleware.assistant.async_assistant`;
- log line includes `bot.ready`;
- no Slack socket reconnect loop.

## Manual Assistant Tests

1. In Slack, open the bot from the app's Messages/Chat UI or AI Assistant
   split-view.
2. Start a new chat.
3. Confirm the bot posts:
   - `New agent conversation ready...`
   - suggested prompts are visible if Slack shows them.
4. Send:

```text
hello, summarize the current repo in one paragraph
```

Expected:

- the Assistant chat title changes to a short form of the first prompt;
- Slack shows an Assistant status such as "is working on your request...";
- the final bot answer appears in the Assistant conversation;
- the response still ends with `**Summary:** ...`.

## Command Tests In Assistant Chat

Run these as separate messages in the same Assistant chat:

```text
cd claude-slack-bot-assistant-threads
```

```text
model gpt-5.5
```

```text
effort high
```

```text
backend codex
```

Expected:

- each command responds inside the Assistant chat;
- settings apply only to that Assistant conversation;
- a second new Assistant chat starts with independent settings/session state.

## Legacy Regression Tests

Verify these still work:

1. Mention the bot in a normal channel.
2. Reply in the created Slack thread.
3. DM the bot outside Assistant chat.
4. Reply in a legacy DM thread.

Expected:

- normal channel and DM flows still route through the original listeners;
- ordinary threaded DMs are not swallowed by the Assistant middleware unless
  their DB record is marked `surface = "slack_assistant"`.

## File And Tool Tests

In an Assistant chat:

1. Upload a small text/image file with a request to inspect it.
2. Ask for a generated `/tmp/` image or chart.
3. Trigger a command that needs approval if using a backend with tool
   confirmations.

Expected:

- attached files are downloaded and referenced in the prompt;
- generated files are uploaded back into the Assistant thread;
- permission buttons still work in the Assistant thread.

## Verification Commands

```bash
python -m pytest tests/test_slack_assistant.py tests/test_database.py tests/test_permissions.py
python -m pytest
python -m ruff check .
python -m pyright
```

## Known Risks

- Slack Assistant features may require a paid workspace or Developer Program
  sandbox.
- `assistant:write` scope changes require reinstalling the app.
- Slack's Assistant middleware matches threaded IMs broadly, so this branch adds
  a DB-surface matcher to avoid consuming ordinary legacy DM thread replies.
- If an Assistant thread was created before this branch saw
  `assistant_thread_started`, its first user message may fall back to the legacy
  DM handler. Starting a fresh Assistant chat avoids that edge case.
