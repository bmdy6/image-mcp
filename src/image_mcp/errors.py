"""Errors safe to expose through CLI and MCP."""


class MediaError(RuntimeError):
    """A bounded message without credentials or upstream response bodies."""
