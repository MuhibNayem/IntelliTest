from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ToolRecord:
    """Recorded information about the last executed tool."""

    name: Optional[str] = None
    input: Optional[Any] = None
    observation: Optional[Any] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class ConversationMessage:
    """Single message in a conversation thread."""

    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "attachments": self.attachments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp")
            or datetime.utcnow().isoformat(),
            attachments=list(data.get("attachments") or []),
        )


@dataclass
class ToolEventRecord:
    """Recorded tool invocation within a conversation."""

    name: str
    status: str
    input: Any = field(default_factory=dict)
    output: Any = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolEventRecord":
        return cls(
            name=data.get("name", ""),
            status=data.get("status", "unknown"),
            input=data.get("input"),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at")
            or datetime.utcnow().isoformat(),
            finished_at=data.get("finished_at"),
            duration_ms=data.get("duration_ms"),
        )


@dataclass
class ConversationThread:
    """Named conversation thread with messages and tool history."""

    thread_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages: List[ConversationMessage] = field(default_factory=list)
    tool_events: List[ToolEventRecord] = field(default_factory=list)

    def add_message(self, message: ConversationMessage) -> None:
        self.messages.append(message)

    def add_tool_event(self, event: ToolEventRecord) -> None:
        self.tool_events.append(event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "messages": [msg.to_dict() for msg in self.messages],
            "tool_events": [event.to_dict() for event in self.tool_events],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationThread":
        thread = cls(
            thread_id=data.get("thread_id", "default"),
            created_at=data.get("created_at")
            or datetime.utcnow().isoformat(),
            metadata=dict(data.get("metadata") or {}),
        )
        for message in data.get("messages") or []:
            thread.add_message(ConversationMessage.from_dict(message))
        for event in data.get("tool_events") or []:
            thread.add_tool_event(ToolEventRecord.from_dict(event))
        return thread


@dataclass
class SnippetRecord:
    snippet_id: int
    file_path: str
    preview: str
    content: str


@dataclass
class SessionManager:
    """Track interactive session state to support contextual follow-ups."""

    project_root: Path
    storage_path: Path = field(init=False)
    last_user_input: Optional[str] = None
    last_agent_response: Optional[str] = None
    last_file_path: Optional[Path] = None
    last_snippet: Optional[str] = None
    last_tool: ToolRecord = field(default_factory=ToolRecord)
    snippets: List[SnippetRecord] = field(default_factory=list)
    max_snippets: int = 10
    next_snippet_id: int = 1
    current_tool_events: List[ToolRecord] = field(default_factory=list)
    threads: Dict[str, ConversationThread] = field(default_factory=dict)
    active_thread_id: str = "interactive"
    workspace_directories: List[str] = field(default_factory=list)
    editing_mode: str = "emacs"

    def __post_init__(self) -> None:
        storage_dir = self.project_root / ".aitestagent"
        storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = storage_dir / "session_state.json"
        self._load()
        # Ensure at least one default thread exists
        if self.active_thread_id not in self.threads:
            self.start_thread(self.active_thread_id)

    def update_user_input(self, user_input: str) -> None:
        self.last_user_input = user_input
        self.save()

    def start_command(self, user_input: str) -> None:
        self.last_user_input = user_input
        self.current_tool_events = []
        self.save()

    def update_agent_response(self, response: str) -> None:
        self.last_agent_response = response
        self.save()

    def record_tool_start(self, name: str, tool_input: Any) -> None:
        record = ToolRecord(name=name, input=tool_input, success=True)
        self.last_tool = record
        self.current_tool_events.append(record)
        self.save()

    def record_tool_result(self, observation: Any) -> None:
        self.last_tool.observation = observation
        self.last_tool.success = True
        if self.last_tool.name == "read_file" and isinstance(observation, str):
            identifier = self._extract_identifier(self.last_tool.input)
            resolved = None
            if identifier:
                resolved = self._resolve_identifier(identifier)
                if resolved:
                    self.last_file_path = resolved
            self.last_snippet = observation[:1000]
            file_for_snippet = str(resolved) if resolved else (identifier or "unknown")
            self._add_snippet(file_for_snippet, observation)
        self.save()
        if self.active_thread_id in self.threads:
            event = ToolEventRecord(
                name=self.last_tool.name or "unknown",
                status="success",
                input=self._serialize_value(self.last_tool.input) or {},
                output=self._serialize_value(observation) or {},
            )
            self.threads[self.active_thread_id].add_tool_event(event)
            self.save()

    def record_tool_error(self, error: str) -> None:
        self.last_tool.success = False
        self.last_tool.error = error
        self.save()
        if self.active_thread_id in self.threads:
            event = ToolEventRecord(
                name=self.last_tool.name or "unknown",
                status="error",
                input=self._serialize_value(self.last_tool.input) or {},
                output={},
                error=error,
            )
            self.threads[self.active_thread_id].add_tool_event(event)
            self.save()

    def start_thread(self, thread_id: str, metadata: Optional[Dict[str, Any]] = None) -> ConversationThread:
        """Create a new conversation thread or return an existing one."""
        thread = self.threads.get(thread_id)
        if thread is None:
            thread = ConversationThread(thread_id=thread_id, metadata=metadata or {})
            self.threads[thread_id] = thread
            self.save()
        if metadata:
            thread.metadata.update(metadata)
        self.active_thread_id = thread_id
        self.save()
        return thread

    def list_threads(self) -> List[str]:
        """Return identifiers for all known threads."""
        return list(self.threads.keys())

    def get_thread(self, thread_id: Optional[str] = None) -> Optional[ConversationThread]:
        """Fetch a conversation thread by id (defaults to active)."""
        target_id = thread_id or self.active_thread_id
        return self.threads.get(target_id)

    def append_message(
        self,
        role: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
    ) -> None:
        """Append a message to the given conversation thread."""
        thread = self.get_thread(thread_id)
        if thread is None:
            thread = self.start_thread(thread_id or self.active_thread_id)
        thread.add_message(
            ConversationMessage(
                role=role,
                content=content,
                attachments=attachments or [],
            )
        )
        self.save()

    def save_checkpoint(self, tag: str, thread_id: Optional[str] = None) -> Optional[Path]:
        """Persist a checkpoint of the current conversation to disk."""
        thread = self.get_thread(thread_id)
        if thread is None:
            return None
        checkpoint_path = self._checkpoint_path(tag)
        payload = {
            "thread": thread.to_dict(),
            "created_at": datetime.utcnow().isoformat(),
            "tag": tag,
        }
        checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return checkpoint_path

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """Return metadata for stored checkpoints."""
        checkpoints_dir = self.storage_path.parent / "checkpoints"
        if not checkpoints_dir.exists():
            return []
        entries: List[Dict[str, Any]] = []
        for file_path in sorted(checkpoints_dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries.append(
                {
                    "tag": data.get("tag") or file_path.stem,
                    "thread_id": data.get("thread", {}).get("thread_id", ""),
                    "created_at": data.get("created_at"),
                    "path": str(file_path),
                }
            )
        return entries

    def load_checkpoint(self, tag: str) -> Optional[str]:
        """Restore a checkpoint into the current session."""
        checkpoint_path = self._checkpoint_path(tag)
        if not checkpoint_path.exists():
            return None
        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        thread_data = data.get("thread")
        if not thread_data:
            return None
        thread = ConversationThread.from_dict(thread_data)
        self.threads[thread.thread_id] = thread
        self.active_thread_id = thread.thread_id
        self.save()
        return thread.thread_id

    def delete_checkpoint(self, tag: str) -> bool:
        """Delete an existing checkpoint."""
        checkpoint_path = self._checkpoint_path(tag)
        try:
            checkpoint_path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def export_checkpoint(self, tag: str, destination: Union[str, Path]) -> Optional[Path]:
        """Copy checkpoint JSON to a user-specified destination."""
        checkpoint_path = self._checkpoint_path(tag)
        if not checkpoint_path.exists():
            return None
        destination_path = Path(destination).expanduser()
        if not destination_path.is_absolute():
            destination_path = (self.project_root / destination_path).resolve()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            checkpoint_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return destination_path

    def add_directory(self, directory: Union[str, Path]) -> Path:
        """Track additional workspace directories."""
        path = Path(directory).expanduser()
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        else:
            path = path.resolve()
        path_str = str(path)
        if path_str not in self.workspace_directories:
            self.workspace_directories.append(path_str)
            self.save()
        return path

    def list_directories(self) -> List[str]:
        """Return tracked workspace directories."""
        return list(self.workspace_directories)

    def set_editing_mode(self, mode: str) -> None:
        """Persist preferred editing mode."""
        self.editing_mode = mode
        self.save()

    def record_summary(self, summary: str, thread_id: Optional[str] = None) -> None:
        """Store a summary for the specified thread."""
        thread = self.get_thread(thread_id)
        if not thread:
            return
        thread.metadata["summary"] = summary
        self.save()

    def export_thread(
        self,
        destination: Union[str, Path],
        thread_id: Optional[str] = None,
    ) -> Optional[Path]:
        """Export a thread to a file (Markdown by default, or JSON by extension)."""
        thread = self.get_thread(thread_id)
        if not thread:
            return None

        destination_path = Path(destination).expanduser()
        if not destination_path.is_absolute():
            destination_path = (self.project_root / destination_path).resolve()
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = destination_path.suffix.lower()
        if suffix == ".json":
            payload = thread.to_dict()
            destination_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            lines: List[str] = []
            for message in thread.messages:
                header = f"### {message.role.capitalize()} ({message.timestamp})"
                lines.append(header)
                lines.append("")
                lines.append(message.content)
                lines.append("")
            content = "\n".join(lines).strip() + "\n"
            destination_path.write_text(content, encoding="utf-8")
        return destination_path

    def _add_snippet(self, file_path: str, content: str) -> None:
        preview_lines = [line.rstrip() for line in content.splitlines()[:6]]
        preview = "\n".join(preview_lines)
        snippet = SnippetRecord(
            snippet_id=self.next_snippet_id,
            file_path=file_path,
            preview=preview,
            content=content,
        )
        self.next_snippet_id += 1
        self.snippets.append(snippet)
        if len(self.snippets) > self.max_snippets:
            self.snippets.pop(0)

    def _extract_identifier(self, tool_input: Any) -> Optional[str]:
        if tool_input is None:
            return None
        if isinstance(tool_input, dict):
            for key in ("file_path", "path", "filename", "name", "value", "target"):
                value = tool_input.get(key)
                if value:
                    return str(value)
        else:
            return str(tool_input)
        return None

    def _resolve_identifier(self, identifier: str) -> Optional[Path]:
        candidate = Path(identifier)
        if not candidate.is_absolute():
            candidate = (self.project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if candidate.exists():
            return candidate
        return None

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        self.last_user_input = data.get("last_user_input")
        self.last_agent_response = data.get("last_agent_response")

        last_file = data.get("last_file_path")
        if last_file:
            self.last_file_path = Path(last_file)

        self.last_snippet = data.get("last_snippet")

        tool_data = data.get("last_tool", {})
        if isinstance(tool_data, dict):
            self.last_tool = ToolRecord(
                name=tool_data.get("name"),
                input=tool_data.get("input"),
                observation=tool_data.get("observation"),
                success=tool_data.get("success", True),
                error=tool_data.get("error"),
            )

        snippets_data = data.get("snippets", [])
        if isinstance(snippets_data, list):
            self.snippets = [
                SnippetRecord(
                    snippet_id=entry.get("snippet_id", index + 1),
                    file_path=entry.get("file_path", ""),
                    preview=entry.get("preview", ""),
                    content=entry.get("content", ""),
                )
                for index, entry in enumerate(snippets_data)
            ]
        self.next_snippet_id = data.get("next_snippet_id", len(self.snippets) + 1)
        threads_data = data.get("threads", {})
        self.active_thread_id = data.get("active_thread_id", "interactive")
        if isinstance(threads_data, dict):
            self.threads = {
                thread_id: ConversationThread.from_dict(thread_data or {})
                for thread_id, thread_data in threads_data.items()
            }
        else:
            # Backwards compatibility for list representations
            thread_entries = {}
            if isinstance(threads_data, list):
                for entry in threads_data:
                    if isinstance(entry, dict):
                        thread = ConversationThread.from_dict(entry)
                        thread_entries[thread.thread_id] = thread
            self.threads = thread_entries
        if not self.threads:
            self.start_thread(self.active_thread_id)
        self.workspace_directories = data.get("workspace_directories", [])
        self.editing_mode = data.get("editing_mode", "emacs")

    def save(self) -> None:
        payload = {
            "last_user_input": self.last_user_input,
            "last_agent_response": self.last_agent_response,
            "last_file_path": str(self.last_file_path) if self.last_file_path else None,
            "last_snippet": self.last_snippet,
            "last_tool": {
                "name": self.last_tool.name,
                "input": self._serialize_value(self.last_tool.input),
                "observation": self._serialize_value(self.last_tool.observation),
                "success": self.last_tool.success,
                "error": self.last_tool.error,
            },
            "snippets": [
                {
                    "snippet_id": snippet.snippet_id,
                    "file_path": snippet.file_path,
                    "preview": snippet.preview,
                    "content": snippet.content,
                }
                for snippet in self.snippets
            ],
            "next_snippet_id": self.next_snippet_id,
            "threads": {
                thread_id: thread.to_dict() for thread_id, thread in self.threads.items()
            },
            "active_thread_id": self.active_thread_id,
            "workspace_directories": self.workspace_directories,
            "editing_mode": self.editing_mode,
        }
        try:
            self.storage_path.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass

    def _checkpoint_path(self, tag: str) -> Path:
        checkpoints_dir = self.storage_path.parent / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        safe_tag = tag.replace(" ", "_")
        return checkpoints_dir / f"{safe_tag}.json"

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    def overwrite_last_user_input(self, value: Optional[str]) -> None:
        self.last_user_input = value
        self.save()

    def get_snippet(self, snippet_id: int) -> Optional[SnippetRecord]:
        for snippet in self.snippets:
            if snippet.snippet_id == snippet_id:
                return snippet
        return None

    def list_snippets(self) -> List[SnippetRecord]:
        return list(self.snippets)

    def get_tool_history(self) -> List[ToolRecord]:
        return list(self.current_tool_events)
