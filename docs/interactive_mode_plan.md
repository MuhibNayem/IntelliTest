# Interactive Mode Implementation Plan

This plan outlines the milestones, tasks, and subtasks required to deliver a production-grade interactive mode that mirrors the Google Gemini CLI feature set.

## Milestone 1: Product Requirements & Architecture

- **Task 1.1: Capture Detailed Requirements**
  - Subtask 1.1.1: Catalogue Gemini CLI user flows (chat, slash commands, bang shell mode, file injections, MCP tooling).
  - Subtask 1.1.2: Document feature parity matrix highlighting mandatory vs optional parity items.
  - Subtask 1.1.3: Identify constraints posed by existing `ai-test-agent` subsystems (LLM access, file sandboxing, async runtime).
- **Task 1.2: Technical Design Blueprint**
  - Subtask 1.2.1: Draft architecture diagram for interactive session loop, command parser, tool dispatchers, and persistence layers.
  - Subtask 1.2.2: Specify extensibility points for custom commands and MCP-style integrations.
  - Subtask 1.2.3: Review design with maintainers and adjust based on feedback.
- **Task 1.3: Dependencies & Environment Audit**
  - Subtask 1.3.1: Evaluate leveraging `prompt_toolkit` for interactive UI (key bindings, history, autocompletion).
  - Subtask 1.3.2: Assess storage layout for session data (checkpoints, settings, history).
  - Subtask 1.3.3: Define configuration migration strategy for new settings files (e.g., `~/.aitestagent/settings.json`).

## Milestone 2: Core Session Loop & Command Dispatcher

- **Task 2.1: Implement Session Manager**
  - Subtask 2.1.1: Extend `SessionManager` to track conversation threads, context stack, and tool logs.
  - Subtask 2.1.2: Add persistence hooks for automatic checkpointing before mutating actions.
  - Subtask 2.1.3: Provide APIs for restoring sessions by tag or timestamp.
- **Task 2.2: Build REPL Engine**
  - Subtask 2.2.1: Integrate `prompt_toolkit` line editor with history navigation, multiline input, and key bindings.
  - Subtask 2.2.2: Surface model and workspace status indicators in the prompt footer.
  - Subtask 2.2.3: Implement graceful shutdown (exit/quit commands, signal handling).
- **Task 2.3: Command Parsing & Dispatch**
  - Subtask 2.3.1: Implement tokenizer that differentiates slash (`/`), at (`@`), bang (`!`), and plain prompts.
  - Subtask 2.3.2: Route parsed commands to dedicated handlers with structured error reporting.
  - Subtask 2.3.3: Add telemetry hooks for command usage analytics (optional/feature-flagged).

## Milestone 3: Slash Command Framework

- **Task 3.1: Core Slash Commands**
  - Subtask 3.1.1: `/help`, `/bug`, `/clear`, `/copy`, `/compress` handlers with parity to Gemini CLI behavior.
  - Subtask 3.1.2: `/chat` subcommands for `save`, `resume`, `list`, `delete`, `share`.
  - Subtask 3.1.3: `/extensions`, `/editor`, `/directory` (`add`, `show`) support.
- **Task 3.2: MCP & Settings Management**
  - Subtask 3.2.1: Implement `/mcp` (`list`, `desc`, `schema`, `auth`) wired into MCP registry.
  - Subtask 3.2.2: Add `/settings` read/write commands syncing with new settings store.
  - Subtask 3.2.3: Support `/init` for generating `AITESTAGENT.md` contextual files analogous to `GEMINI.md`.
- **Task 3.3: Mode Toggles & Shortcuts**
  - Subtask 3.3.1: Introduce `/mode vim` with persisted preference and `[NORMAL]/[INSERT]` indicator.
  - Subtask 3.3.2: Register keyboard shortcuts (Ctrl+L clear, Ctrl+Z undo, Ctrl+Shift+Z redo).
  - Subtask 3.3.3: Build `/history` and `/log` commands for session review.

## Milestone 4: At Commands & Context Management

- **Task 4.1: File & Directory Injection**
  - Subtask 4.1.1: Implement `@<path>` expansion using git-aware filtering and size limits.
  - Subtask 4.1.2: Provide feedback on skipped or truncated files; handle binary detection.
  - Subtask 4.1.3: Integrate with session snippets to allow reuse in follow-up prompts.
- **Task 4.2: Context Files & Trusted Folders**
  - Subtask 4.2.1: Support project-level `AITESTAGENT.md` auto-loading for persistent instructions.
  - Subtask 4.2.2: Implement trusted folder policies mirroring Gemini CLI sandbox modes.
  - Subtask 4.2.3: Expose `/context` commands to inspect, enable, disable context sources.
- **Task 4.3: Large Input Handling**
  - Subtask 4.3.1: Add streaming uploads for big files with progress indicators.
  - Subtask 4.3.2: Introduce chunked summarisation when token limits are at risk.
  - Subtask 4.3.3: Provide `/compress` context summaries for long sessions.

## Milestone 5: Bang Commands & Tool Execution

- **Task 5.1: Shell Passthrough**
  - Subtask 5.1.1: Add `!` single-command execution with sandbox-aware subprocess runner.
  - Subtask 5.1.2: Implement shell mode toggle (`!` lone) with exit cues and prompt styling.
  - Subtask 5.1.3: Ensure `AITEST_AGENT=1` (analogous to `GEMINI_CLI=1`) environment variable injection.
- **Task 5.2: Tool Registry & Invocation**
  - Subtask 5.2.1: Expose built-in tools (list/read/write files, run commands, analyze, generate tests, run tests, report) through structured tool calls.
  - Subtask 5.2.2: Implement tool call visualisation matching Gemini CLI (tool card, arguments, status, duration).
  - Subtask 5.2.3: Support consecutive tool chaining with dependency-aware ordering.
- **Task 5.3: Web & Search Integrations**
  - Subtask 5.3.1: Implement web fetch tool (HTTP GET with safety filters).
  - Subtask 5.3.2: Integrate optional search grounding API (configurable API key).
  - Subtask 5.3.3: Provide `/tools` command to describe available tools and usage limits.

## Milestone 6: Persistence, Checkpointing & Extensibility

- **Task 6.1: Conversation Checkpoints**
  - Subtask 6.1.1: Auto-save checkpoints before mutating tool actions (writes, shell commands).
  - Subtask 6.1.2: Implement incremental diff storage for large conversations.
  - Subtask 6.1.3: Add `/checkpoint` command for manual capture and restoration.
- **Task 6.2: Settings & Profiles**
  - Subtask 6.2.1: Support layered settings (global `~/.aitestagent/settings.json`, project overrides, session overrides).
  - Subtask 6.2.2: Provide schema validation and migration for settings files.
  - Subtask 6.2.3: Implement profiles (e.g., enterprise, sandbox) selecting default policies.
- **Task 6.3: MCP & Extension SDK**
  - Subtask 6.3.1: Implement MCP client with connection lifecycle management.
  - Subtask 6.3.2: Provide SDK for authoring custom slash/at/bang commands and tools.
  - Subtask 6.3.3: Publish sample extensions (GitHub, Slack) as reference implementations.

## Milestone 7: Quality Assurance & Launch

- **Task 7.1: Testing Strategy**
  - Subtask 7.1.1: Add unit tests for parser, command handlers, and session manager.
  - Subtask 7.1.2: Create integration tests simulating full interactive sessions.
  - Subtask 7.1.3: Establish regression suite covering sandbox policies and tool safety.
- **Task 7.2: Documentation & Tutorials**
  - Subtask 7.2.1: Update `docs/CLI_REFERENCE.md` and `docs/usage.md` with interactive mode details.
  - Subtask 7.2.2: Produce quickstart walkthrough with GIFs or asciinema recordings.
  - Subtask 7.2.3: Write migration notes for existing users upgrading to the new interactive mode.
- **Task 7.3: Release Readiness**
  - Subtask 7.3.1: Define feature flags or preview channel for incremental roll-out.
  - Subtask 7.3.2: Collect beta feedback and triage high-priority issues.
  - Subtask 7.3.3: Finalise version bump, changelog, and announcement copy.
