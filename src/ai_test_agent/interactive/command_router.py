from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class CommandType(Enum):
    """Supported interactive command categories."""

    EMPTY = auto()
    EXIT = auto()
    SLASH = auto()
    AT = auto()
    BANG = auto()
    BANG_TOGGLE = auto()
    PLAIN = auto()


@dataclass
class ParsedCommand:
    """Parsed representation of a user input line."""

    raw: str
    type: CommandType
    name: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    payload: Optional[str] = None

    @property
    def is_exit(self) -> bool:
        return self.type == CommandType.EXIT


class CommandRouter:
    """Parse raw user input into structured command objects."""

    EXIT_KEYWORDS = {"exit", "quit", ":q"}

    def parse(self, text: str, shell_mode: bool = False) -> ParsedCommand:
        stripped = (text or "").strip()
        if not stripped:
            return ParsedCommand(raw=text, type=CommandType.EMPTY)

        lowered = stripped.lower()
        if lowered in self.EXIT_KEYWORDS:
            return ParsedCommand(raw=text, type=CommandType.EXIT)

        if shell_mode:
            if stripped == "!":
                return ParsedCommand(raw=text, type=CommandType.BANG_TOGGLE)
            return ParsedCommand(
                raw=text,
                type=CommandType.BANG,
                name="shell",
                payload=stripped,
            )

        if stripped.startswith("/"):
            return self._parse_slash_command(stripped)

        if stripped.startswith("@"):
            return self._parse_at_command(stripped)

        if stripped.startswith("!"):
            return self._parse_bang_command(stripped)

        return ParsedCommand(
            raw=text,
            type=CommandType.PLAIN,
            payload=text,
        )

    def _parse_slash_command(self, text: str) -> ParsedCommand:
        body = text[1:].strip()
        if not body:
            return ParsedCommand(raw=text, type=CommandType.SLASH, name="")
        parts = body.split()
        command = parts[0].lower()
        args = parts[1:]
        return ParsedCommand(
            raw=text,
            type=CommandType.SLASH,
            name=command,
            arguments=args,
            payload=" ".join(args),
        )

    def _parse_at_command(self, text: str) -> ParsedCommand:
        body = text[1:]
        if not body:
            return ParsedCommand(raw=text, type=CommandType.AT, name="")
        if " " in body:
            path, remainder = body.split(" ", 1)
            remainder = remainder.strip()
        else:
            path, remainder = body, ""
        return ParsedCommand(
            raw=text,
            type=CommandType.AT,
            name=path.strip(),
            payload=remainder,
        )

    def _parse_bang_command(self, text: str) -> ParsedCommand:
        if text == "!":
            return ParsedCommand(raw=text, type=CommandType.BANG_TOGGLE)
        command = text[1:].strip()
        return ParsedCommand(
            raw=text,
            type=CommandType.BANG,
            name="shell",
            payload=command,
        )

    @staticmethod
    def standard_slash_commands() -> List[str]:
        return [
            "help",
            "history",
            "clear",
            "copy",
            "compress",
            "chat",
            "checkpoint",
            "settings",
            "extensions",
            "mode",
            "directory",
            "tools",
            "exit",
            "quit",
        ]
