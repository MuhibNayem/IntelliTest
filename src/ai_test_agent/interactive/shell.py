from __future__ import annotations

import asyncio
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from ..agent.agent import TestAutomationAgent
from ..agent.session import SessionManager
from ..config import Settings
from .command_router import CommandRouter, CommandType, ParsedCommand


class InteractiveShell:
    """Interactive REPL loop for ai-test-agent."""

    def __init__(
        self,
        agent: TestAutomationAgent,
        session_manager: SessionManager,
        settings: Settings,
        project_root: Path,
    ) -> None:
        self.agent = agent
        self.session_manager = session_manager
        self.settings = settings
        self.project_root = Path(project_root)
        self.console = Console(highlight=False, soft_wrap=True)
        self.router = CommandRouter()
        self.shell_mode = False
        self.active_thread_id = session_manager.active_thread_id or "interactive"
        self.session_manager.start_thread(
            self.active_thread_id,
            metadata={"project_root": str(self.project_root)},
        )

        self.history_path = self.session_manager.storage_path.parent / "history.txt"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.editing_mode_label = self.session_manager.editing_mode or "emacs"
        self.editing_mode = self._editing_mode_from_label(self.editing_mode_label)
        self.prompt_session = self._build_prompt_session()

    def run(self) -> None:
        """Run the REPL loop."""
        self.console.print(
            "[bold cyan]Interactive mode ready.[/bold cyan] "
            "Type /help for assistance, /exit or Ctrl+D to leave."
        )

        while True:
            try:
                prompt = self._build_prompt()
                with patch_stdout():
                    user_input = self.prompt_session.prompt(prompt)
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Exiting interactive mode.[/yellow]")
                break

            parsed = self.router.parse(user_input, shell_mode=self.shell_mode)

            if parsed.type == CommandType.EMPTY:
                continue
            if parsed.type == CommandType.EXIT:
                break

            self.session_manager.start_command(user_input)

            if parsed.type == CommandType.SLASH:
                if self._handle_slash(parsed):
                    break
                continue

            if parsed.type == CommandType.AT:
                self._handle_at(parsed)
                continue

            if parsed.type == CommandType.BANG_TOGGLE:
                self.shell_mode = not self.shell_mode
                mode_text = "enabled" if self.shell_mode else "disabled"
                self.console.print(f"[green]Shell mode {mode_text}.[/green]")
                continue

            if parsed.type == CommandType.BANG:
                self._handle_bang(parsed)
                continue

            if parsed.type == CommandType.PLAIN:
                self._handle_plain(parsed)
                continue

            self.console.print(f"[red]Unsupported command type: {parsed.type}[/red]")

    def _build_prompt(self) -> str:
        if self.shell_mode:
            return "shell> "
        model_label = self.settings.llm_model_name
        mode_indicator = "vim" if self.editing_mode == EditingMode.VI else ""
        suffix = f" [{mode_indicator}]" if mode_indicator else ""
        return f"ai-test-agent ({model_label}){suffix}> "

    def _build_prompt_session(self) -> PromptSession:
        return PromptSession(
            history=FileHistory(str(self.history_path)),
            editing_mode=self.editing_mode,
        )

    @staticmethod
    def _editing_mode_from_label(label: str) -> EditingMode:
        normalized = (label or "").lower()
        if normalized in {"vim", "vi"}:
            return EditingMode.VI
        return EditingMode.EMACS

    def _set_editing_mode(self, label: str) -> None:
        normalized = label.lower()
        target_label = "vim" if normalized in {"vim", "vi"} else "emacs"
        new_mode = self._editing_mode_from_label(target_label)
        if new_mode == self.editing_mode:
            self.console.print(f"[cyan]Input mode already set to {target_label}.[/cyan]")
            return
        self.editing_mode_label = target_label
        self.editing_mode = new_mode
        self.session_manager.set_editing_mode(target_label)
        self.prompt_session = self._build_prompt_session()
        self.console.print(f"[green]Input mode switched to {target_label}.[/green]")

    def _handle_plain(self, parsed: ParsedCommand) -> None:
        if not parsed.payload:
            return
        self._send_to_agent(parsed.payload)

    def _handle_at(self, parsed: ParsedCommand) -> None:
        if not parsed.name:
            self.console.print("[yellow]Usage: @<path> [optional prompt][/yellow]")
            return

        attachments = [{"type": "file", "path": parsed.name}]
        try:
            content = asyncio.run(self.agent.file_tools.read_file(parsed.name))
        except FileNotFoundError:
            self.console.print(f"[red]File not found: {parsed.name}[/red]")
            return
        except Exception as exc:
            self.console.print(f"[red]Failed to read {parsed.name}: {exc}[/red]")
            return

        prompt_text = parsed.payload or ""
        composed_prompt = (
            f"{prompt_text}\n\n"
            f"```file:{parsed.name}\n{content}\n```"
        ).strip()
        self._send_to_agent(composed_prompt, attachments=attachments)

    def _handle_bang(self, parsed: ParsedCommand) -> None:
        command = parsed.payload or ""
        if not command:
            self.console.print("[yellow]Usage: !<command>[/yellow]")
            return

        self.session_manager.record_tool_start(
            "run_command",
            {"command": command, "cwd": str(self.project_root)},
        )
        exit_code, stdout, stderr = asyncio.run(
            self.agent.file_tools.run_command(command)
        )
        observation = {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }
        if exit_code == 0:
            self.console.print(f"[green]$ {command}[/green]")
            if stdout:
                self.console.print(stdout.rstrip())
            if stderr:
                self.console.print(f"[yellow]{stderr.rstrip()}[/yellow]")
            self.session_manager.record_tool_result(observation)
        else:
            self.console.print(f"[red]Command failed (exit {exit_code}).[/red]")
            if stdout:
                self.console.print(stdout.rstrip())
            if stderr:
                self.console.print(f"[red]{stderr.rstrip()}[/red]")
            self.session_manager.record_tool_error(stderr or "command failed")

    def _handle_slash(self, parsed: ParsedCommand) -> bool:
        command = parsed.name or ""
        if command in {"exit", "quit"}:
            return True

        if command == "help":
            self._print_help()
            return False

        if command == "history":
            self._print_history()
            return False

        if command == "clear":
            self.console.clear()
            return False

        if command == "copy":
            self._handle_copy_command(parsed.arguments)
            return False

        if command == "compress":
            self._compress_conversation()
            return False

        if command == "checkpoint":
            tag = parsed.payload or "checkpoint"
            path = self.session_manager.save_checkpoint(tag, thread_id=self.active_thread_id)
            if path:
                self.console.print(f"[green]Checkpoint saved to {path}[/green]")
            else:
                self.console.print("[red]Unable to create checkpoint.[/red]")
            return False

        if command == "chat":
            self._handle_chat_command(parsed.arguments)
            return False

        if command == "directory":
            self._handle_directory_command(parsed.arguments)
            return False

        if command == "mode":
            self._handle_mode_command(parsed.arguments)
            return False

        self.console.print(
            f"[yellow]Unsupported /{command} command (coming soon).[/yellow]"
        )
        return False

    def _handle_chat_command(self, arguments: List[str]) -> None:
        if not arguments:
            self.console.print(
                "[yellow]Usage: /chat <list|new|use|save|resume|delete|share|checkpoints> [...][/yellow]"
            )
            return

        subcommand = arguments[0].lower()
        if subcommand == "list":
            thread_ids = self.session_manager.list_threads()
            if not thread_ids:
                self.console.print("[yellow]No threads available.[/yellow]")
                return
            for thread_id in thread_ids:
                marker = "*" if thread_id == self.active_thread_id else " "
                thread = self.session_manager.get_thread(thread_id)
                summary = thread.metadata.get("summary", "") if thread else ""
                summary_note = " (summary saved)" if summary else ""
                self.console.print(f"{marker} {thread_id}{summary_note}")
            return

        if subcommand == "new":
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat new <thread_id>[/yellow]")
                return
            thread_id = arguments[1]
            self.session_manager.start_thread(thread_id, metadata={"created_via": "interactive"})
            self.active_thread_id = thread_id
            self.console.print(f"[green]Created and switched to thread '{thread_id}'.[/green]")
            return

        if subcommand == "use":
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat use <thread_id>[/yellow]")
                return
            thread_id = arguments[1]
            if thread_id not in self.session_manager.list_threads():
                self.console.print(f"[red]Unknown thread '{thread_id}'.[/red]")
                return
            self.active_thread_id = thread_id
            self.session_manager.start_thread(thread_id)
            self.console.print(f"[green]Switched to thread '{thread_id}'.[/green]")
            return

        if subcommand == "save":
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat save <tag>[/yellow]")
                return
            tag = arguments[1]
            path = self.session_manager.save_checkpoint(tag, thread_id=self.active_thread_id)
            if path:
                self.console.print(f"[green]Checkpoint '{tag}' saved to {path}.[/green]")
            else:
                self.console.print("[red]Failed to save checkpoint.[/red]")
            return

        if subcommand in {"resume", "load"}:
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat resume <tag>[/yellow]")
                return
            tag = arguments[1]
            thread_id = self.session_manager.load_checkpoint(tag)
            if thread_id:
                self.active_thread_id = thread_id
                self.console.print(f"[green]Restored checkpoint '{tag}' (thread '{thread_id}').[/green]")
            else:
                self.console.print(f"[red]Checkpoint '{tag}' not found.[/red]")
            return

        if subcommand == "delete":
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat delete <tag>[/yellow]")
                return
            tag = arguments[1]
            if self.session_manager.delete_checkpoint(tag):
                self.console.print(f"[green]Deleted checkpoint '{tag}'.[/green]")
            else:
                self.console.print(f"[red]Checkpoint '{tag}' not found or could not be deleted.[/red]")
            return

        if subcommand in {"share", "export"}:
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /chat share <output_path> [checkpoint_tag][/yellow]")
                return
            output_path = arguments[1]
            tag = arguments[2] if len(arguments) > 2 else None
            if tag:
                exported = self.session_manager.export_checkpoint(tag, output_path)
            else:
                exported = self.session_manager.export_thread(output_path, thread_id=self.active_thread_id)
            if exported:
                self.console.print(f"[green]Conversation exported to {exported}.[/green]")
            else:
                self.console.print("[red]Failed to export conversation.[/red]")
            return

        if subcommand in {"checkpoints", "ls"}:
            records = self.session_manager.list_checkpoints()
            if not records:
                self.console.print("[yellow]No checkpoints stored yet.[/yellow]")
                return
            for record in records:
                self.console.print(
                    f"- {record['tag']} (thread: {record['thread_id']}, saved {record.get('created_at', 'unknown')})"
                )
            return

        self.console.print(f"[yellow]Unsupported /chat command: {subcommand}[/yellow]")

    def _handle_copy_command(self, arguments: List[str]) -> None:
        target = arguments[0].lower() if arguments else "last"
        thread = self.session_manager.get_thread(self.active_thread_id)

        if target in {"last", "response", "assistant"}:
            text = self.session_manager.last_agent_response or ""
        elif target in {"prompt", "input", "user"}:
            text = self.session_manager.last_user_input or ""
        elif target in {"history", "all"} and thread:
            text = "\n\n".join(f"{msg.role}: {msg.content}" for msg in thread.messages)
        else:
            self.console.print(
                "[yellow]Usage: /copy [last|prompt|history][/yellow]"
            )
            return

        if not text.strip():
            self.console.print("[yellow]Nothing to copy yet.[/yellow]")
            return

        if self._copy_to_clipboard(text):
            self.console.print("[green]Copied to clipboard.[/green]")
        else:
            self.console.print(
                "[red]Clipboard utility not available. Install 'pyperclip' or configure a platform clipboard tool.[/red]"
            )

    def _copy_to_clipboard(self, text: str) -> bool:
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            return True
        except Exception:
            pass

        system = platform.system()
        commands: List[List[str]]
        if system == "Darwin":
            commands = [["pbcopy"]]
        elif system == "Linux":
            commands = [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
        elif system == "Windows":
            commands = [["clip"]]
        else:
            commands = []

        for command in commands:
            if not shutil.which(command[0]):
                continue
            try:
                proc = subprocess.run(
                    command,
                    input=text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
            except OSError:
                continue
            if proc.returncode == 0:
                return True
        return False

    def _compress_conversation(self) -> None:
        thread = self.session_manager.get_thread(self.active_thread_id)
        if not thread or not thread.messages:
            self.console.print("[yellow]No conversation to compress yet.[/yellow]")
            return

        recent_messages = thread.messages[-20:]
        transcript = "\n".join(f"{msg.role}: {msg.content}" for msg in recent_messages)
        prompt_text = (
            "Summarize the following conversation between a user and the AI Test Agent into concise bullet points. "
            "Highlight key actions, questions, and decisions.\n\n"
            f"{transcript}"
        )

        result = self.agent.run(prompt_text)
        if not result.get("success"):
            self.console.print(
                f"[red]Failed to compress conversation: {result.get('error', 'Unknown error')}[/red]"
            )
            return

        summary = (result.get("result") or "").strip()
        if not summary:
            self.console.print("[yellow]Compression produced an empty summary.[/yellow]")
            return

        self.console.print("[cyan]Conversation summary:[/cyan]")
        self.console.print(summary)
        self.session_manager.record_summary(summary, thread_id=self.active_thread_id)
        self.session_manager.append_message(
            "assistant",
            f"(summary)\n{summary}",
            thread_id=self.active_thread_id,
        )

    def _handle_directory_command(self, arguments: List[str]) -> None:
        if not arguments:
            self.console.print(
                "[yellow]Usage: /directory <add|show> [paths][/yellow]"
            )
            return

        subcommand = arguments[0].lower()
        if subcommand == "add":
            if len(arguments) < 2:
                self.console.print("[yellow]Usage: /directory add <path1>[,<path2>...] [/yellow]")
                return
            raw_paths = " ".join(arguments[1:])
            added_any = False
            for raw_path in raw_paths.split(","):
                candidate = raw_path.strip()
                if not candidate:
                    continue
                resolved = self.session_manager.add_directory(candidate)
                self.console.print(f"[green]Added directory: {resolved}[/green]")
                added_any = True
            if not added_any:
                self.console.print("[yellow]No directories added.[/yellow]")
            return

        if subcommand == "show":
            directories = self.session_manager.list_directories()
            if not directories:
                self.console.print("[yellow]No additional directories configured.[/yellow]")
                return
            self.console.print("[cyan]Tracked directories:[/cyan]")
            for path in directories:
                self.console.print(f"- {path}")
            return

        self.console.print(f"[yellow]Unsupported /directory command: {subcommand}[/yellow]")

    def _handle_mode_command(self, arguments: List[str]) -> None:
        if not arguments:
            self.console.print(
                f"[cyan]Current input mode: {self.editing_mode_label}. Use '/mode vim' or '/mode default'.[/cyan]"
            )
            return

        target = arguments[0].lower()
        if target in {"vim", "vi"}:
            self._set_editing_mode("vim")
        elif target in {"default", "emacs"}:
            self._set_editing_mode("emacs")
        else:
            self.console.print("[yellow]Unsupported mode. Use 'vim' or 'default'.[/yellow]")

    def _print_help(self) -> None:
        commands = CommandRouter.standard_slash_commands()
        self.console.print(
            "[cyan]Available commands:[/cyan] "
            + ", ".join(f"/{cmd}" for cmd in commands)
        )
        self.console.print(
            "Use /chat save|resume to manage checkpoints, /copy to copy responses, /directory add to expand scope."
        )
        self.console.print("Use @<path> to include files, !<cmd> to run shell commands.")

    def _print_history(self, limit: int = 20) -> None:
        thread = self.session_manager.get_thread(self.active_thread_id)
        if not thread or not thread.messages:
            self.console.print("[yellow]No conversation history yet.[/yellow]")
            return
        self.console.print(
            f"[cyan]Showing last {min(limit, len(thread.messages))} messages:[/cyan]"
        )
        for message in thread.messages[-limit:]:
            role = message.role.capitalize()
            timestamp = message.timestamp
            self.console.print(f"[bold]{role}[/bold] [{timestamp}]: {message.content}")

    def _send_to_agent(
        self,
        prompt: str,
        attachments: Optional[List[dict]] = None,
    ) -> None:
        attachments = attachments or []
        self.session_manager.append_message(
            "user",
            prompt,
            attachments=attachments,
            thread_id=self.active_thread_id,
        )
        self.session_manager.update_user_input(prompt)

        assistant_chunks: List[str] = []
        error_message: Optional[str] = None

        for event in self.agent.stream_response(prompt):
            event_type = event.get("type")
            if event_type == "content":
                chunk = event.get("chunk", "")
                assistant_chunks.append(chunk)
                if chunk:
                    self.console.print(chunk, style="green")
                else:
                    self.console.print("")
            elif event_type == "tool":
                self._render_tool_event(event)
            elif event_type == "error":
                error_message = event.get("message", "Unknown error")
                self.console.print(f"[red]{error_message}[/red]")
                break

        if error_message:
            self.session_manager.append_message(
                "assistant",
                f"(error) {error_message}",
                thread_id=self.active_thread_id,
            )
            return

        full_response = "\n".join(assistant_chunks).strip()
        if not full_response:
            full_response = "(no response)"
        self.session_manager.update_agent_response(full_response)
        self.session_manager.append_message(
            "assistant",
            full_response,
            thread_id=self.active_thread_id,
        )

    def _render_tool_event(self, event: Dict[str, str]) -> None:
        """Display tool call information emitted from the agent stream."""
        tool_name = event.get("name", "tool")
        status = event.get("status", "running")
        payload = event.get("payload", "")
        if status == "running":
            self.console.print(f"[cyan]{tool_name}: {payload}[/cyan]")
        elif status == "success":
            self.console.print(f"[green]{tool_name} ✓[/green]")
        elif status == "error":
            self.console.print(f"[red]{tool_name} ✗ {payload}[/red]")
