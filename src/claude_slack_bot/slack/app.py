from __future__ import annotations

from slack_bolt.async_app import AsyncApp

from ..config import Settings
from ..core.coordinator import ThreadCoordinator
from ..core.permissions import PermissionManager
from .assistant import register_assistant
from .listeners import register_listeners


def create_slack_app(
    settings: Settings,
    coordinator: ThreadCoordinator,
    permission_mgr: PermissionManager,
) -> AsyncApp:
    """Create and configure the Slack Bolt async app."""
    app = AsyncApp(token=settings.slack_bot_token)
    if settings.enable_slack_assistant:
        register_assistant(app, coordinator)
    register_listeners(app, coordinator, permission_mgr)
    return app
