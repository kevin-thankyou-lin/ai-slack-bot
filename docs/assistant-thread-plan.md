# Assistant Thread Conversations Plan

## Goal

Move toward Slack conversations that feel like independent agent chats instead
of very long ordinary Slack threads.

Primary implementation is option (1): Slack's native Agents & AI Apps Assistant
conversation surface. This keeps the current agent/session architecture but
lets Slack show each task as a separate Assistant chat with a title, status, and
history entry.

Fallback is option (4): keep the existing Slack-thread engine as the reliable
path if Assistant features are unavailable in the workspace, and add a dedicated
"new conversation" entrypoint later that creates a cleaner legacy Slack surface
without requiring the Assistant feature flag or `assistant:write` scope.

## Slack References

- Bolt Python Assistant middleware:
  https://docs.slack.dev/tools/bolt-python/concepts/using-the-assistant-class/
- `assistant_thread_started` event:
  https://docs.slack.dev/reference/events/assistant_thread_started/
- `assistant.threads.setStatus`:
  https://docs.slack.dev/reference/methods/assistant.threads.setStatus/
- `assistant.threads.setTitle`:
  https://docs.slack.dev/reference/methods/assistant.threads.setTitle/
- `assistant.threads.setSuggestedPrompts`:
  https://docs.slack.dev/reference/methods/assistant.threads.setSuggestedPrompts/

## Current Architecture Notes

- The bot still maps one Slack conversation key to one backend session.
- The existing key is named `thread_ts` throughout the DB and coordinator.
- Legacy channel mentions, DMs, replies, tool approvals, file uploads, polls,
  compacting, stop/reset/done, backend switching, model switching, and cwd
  switching all already work through that key.
- Assistant threads also provide `channel_id` and `thread_ts`, so the
  implementation can reuse most of the current coordinator.

## Implementation Strategy

- Add a persisted `surface` field to `threads`.
- Use `surface = "slack_thread"` for existing behavior.
- Use `surface = "slack_assistant"` for native Slack Assistant chats.
- Register Bolt's `AsyncAssistant` middleware when
  `ENABLE_SLACK_ASSISTANT=true`.
- Handle `assistant_thread_started` by:
  - creating or marking the coordinator thread record as `slack_assistant`;
  - setting a default title;
  - setting suggested prompts;
  - posting a short ready message so Slack's Assistant context store has a
    first bot reply to attach metadata to.
- Handle Assistant user messages by:
  - only accepting messages for persisted `slack_assistant` threads;
  - downloading attached files through the existing Slack file downloader;
  - forwarding the message to the existing `ThreadCoordinator`.
- Use Assistant `set_status` for long-running work and tool activity instead
  of adding extra "Thinking..." messages in Assistant conversations.
- Set the Assistant conversation title from the first user prompt.

## Progress

- [x] Cloned a separate repo to `claude-slack-bot-assistant-threads`.
- [x] Copied `.env` and `src/claude_slack_bot/agent/prompts.py` from the
  original local checkout.
- [x] Created branch `feature/assistant-thread-conversations`.
- [x] Added DB `surface` support with migration default.
- [x] Added Slack Assistant listener module.
- [x] Added `ENABLE_SLACK_ASSISTANT` setting.
- [x] Updated manifest scopes/events for Assistant support.
- [x] Updated copied prompt wording from "Slack thread" to "Slack conversation".
- [x] Added focused unit tests for Assistant surface persistence and matcher
  behavior.
- [x] Run full test suite and lint.
- [x] Run scoped type check on the touched Assistant implementation files.
- [ ] Manual Slack validation in an Assistant-enabled workspace.

## Option (4) Fallback

Use this if Slack Assistant is blocked by plan, workspace settings, app review,
or unexpected API behavior.

- Keep the existing Slack thread flow as the stable execution engine.
- Add an explicit command or shortcut such as `new chat <prompt>` that creates
  a fresh top-level Slack post and links back to prior context when useful.
- Keep all existing per-thread state, permissions, file uploads, and polling.
- Optionally add automatic compact summaries and thread titles so the thread
  list remains scannable.

This fallback has lower Slack-platform risk, but it will not be as clean as the
native Assistant chat history because Slack still represents the conversation as
ordinary messages/threads.
