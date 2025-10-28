# Interactive Mode – Technical Design Blueprint (Milestone 1, Task 2)

This blueprint translates the captured requirements into an architectural plan for the interactive mode. It defines core components, data flows, extensibility points, and integration contracts.

## 1. High-Level Architecture

```
+------------------------------+
| ai-test-agent CLI (`interactive`) |
+------------------------------+
            |
            v
+------------------------------+       +---------------------------+
| InteractiveShell (prompt loop)|<---->| Settings & Profile Manager |
+------------------------------+       +---------------------------+
            |
            v
+------------------------------+       +----------------------------+
| CommandRouter                |<----->| SessionManager (state store)|
+------------------------------+       +----------------------------+
   |      |        |
   |      |        +-------------------------------+
   |      |                                        |
   v      v                                        v
 Slash  At/Bang                              ToolDispatchers
Handlers Handlers                          (local + MCP tools)
                                             |
                                             v
                                   +-----------------------+
                                   | TestAutomationAgent   |
                                   |  (LangGraph pipeline) |
                                   +-----------------------+
```

- **InteractiveShell**: owns the REPL using `prompt_toolkit`, presenting prompts, handling key bindings, streaming model output, and coordinating cancellation.
- **CommandRouter**: parses user input into typed commands (plain prompt, slash, at, bang) and dispatches to handlers.
- **SessionManager**: persists conversation history, checkpoints, tool logs, and metadata on disk; exposes APIs for slash commands.
- **ToolDispatchers**: unified interface around built-in tools and MCP servers; forwards tool calls from LLM outputs or direct commands.
- **Settings & Profile Manager**: loads layered configs (global, project, session), manages trusted folder policies, and surfaces warnings.
- **TestAutomationAgent**: existing LangGraph agent reused for LLM interaction and tool orchestration, wrapped to support streaming responses.

## 2. Key Components & Responsibilities

### 2.1 InteractiveShell
- Initialize `prompt_toolkit` application with:
  - Custom layout (prompt, footer status line, optional tool panels).
  - History and clipboard integration.
  - Key bindings (Ctrl+L, Ctrl+Z, etc.).
- Manage async loop:
  - `run()` coroutine driving the prompt, awaiting user input, delegating to CommandRouter.
  - Handle cancellation (Ctrl+C) with confirmation.
- Stream model output:
  - Use `LangChain` streaming callbacks or incremental writes to display responses as they arrive.
  - Format tool call annotations inline.

### 2.2 CommandRouter
- Tokenize input using deterministic rules:
  - Leading `/`, `@`, `!` (with/without argument).
  - Support quotes, escaped spaces, multiple commands per line (e.g., `/chat save my-tag`).
- Maintain registry of handlers:
  - SlashCommandRegistry: mapping command -> handler function metadata.
  - AtCommandHandler: preprocess file paths, generate prompt payload.
  - BangCommandHandler: differentiate one-shot vs shell mode toggles.
  - PlainPromptHandler: forward to agent with aggregated context.
- Provide structured results/events for UI rendering (success/failure messages).

### 2.3 SessionManager Enhancements
- Data model additions:
  - `ConversationThread` with messages, tool events, checkpoints.
  - `Checkpoint` storing serialized conversation + diff of file changes.
  - `SettingsSnapshot` recorded at session start for reproducibility.
- Persistence:
  - Store under `~/.aitestagent/tmp/<project_hash>/`.
  - Use JSON/MsgPack for logs, optionally compress large transcripts.
  - Support manual/auto retention policies.
- APIs:
  - `save_checkpoint(tag)`, `resume(tag)`, `list_checkpoints()`, `delete(tag)`, `share(path, format)`.
  - `record_tool_call(event)`, `get_tool_history()`.

### 2.4 Settings & Profile Manager
- Layered configuration resolution:
  1. Global: `~/.aitestagent/settings.json`.
  2. Project: `.aitestagent/settings.json`.
  3. Session: CLI overrides / slash commands.
- Provide schema validation (Pydantic) and migration strategy.
- Profiles:
  - `default`, `restricted`, `enterprise` with predetermined sandbox and telemetry policies.
- Trusted folder detection:
  - Maintain allowlist; warn or block risky actions when outside.

### 2.5 Tool Dispatching
- Built-in Tool Adapter:
  - Wrap existing LangChain tools (ReadFileTool, RunCommandTool, etc.) with consistent metadata (name, description, schema).
  - Provide synchronous & async execution interfaces for interactive use.
- MCP Client:
  - Implement Model Context Protocol client to connect to external servers.
  - Manage authentication flows, tool discovery, schema caching.
  - Normalize outputs for display in InteractiveShell.
- Tool Execution Flow:
  1. Model response includes tool call.
  2. CommandRouter dispatches to ToolDispatcher.
  3. Tool execution results recorded in SessionManager, streamed to UI.

### 2.6 Agent Integration
- Refactor `TestAutomationAgent.run()` to support streaming callbacks.
- Expose control over tool availability and conversation ID for multi-thread.
- Provide APIs for:
  - `start_conversation(session_id)`.
  - `send_message(content, context_items)`.
  - `abort()` to cancel long-running operations.

## 3. Data Contracts

### 3.1 Session Log Schema
```jsonc
{
  "version": 1,
  "created_at": "2024-10-28T12:34:56Z",
  "project_root": "/path/to/project",
  "messages": [
    {
      "role": "user",
      "content": "Generate tests for parser.py",
      "timestamp": "2024-10-28T12:35:00Z",
      "attachments": [
        {"type": "file", "path": "src/parser.py", "digest": "sha256:..."}
      ]
    },
    {
      "role": "assistant",
      "content": "...",
      "tool_calls": [
        {
          "name": "AnalyzeProjectTool",
          "arguments": {...},
          "result": {...},
          "duration_ms": 5234,
          "status": "success"
        }
      ]
    }
  ],
  "checkpoints": [
    {"tag": "post-test-gen", "path": ".../checkpoint.json", "created_at": "..."}
  ]
}
```

### 3.2 Settings Schema Additions
```jsonc
{
  "interactive": {
    "default_mode": "default|vim",
    "trusted_folders": ["~/Projects", "/work/repos"],
    "profiles": {
      "default": {"sandbox": "workspace-write", "telemetry": "opt-in"},
      "restricted": {"sandbox": "read-only", "telemetry": "disabled"}
    },
    "mcp_servers": [
      {"name": "github", "transport": "stdio", "command": "path/to/server", "env": {}}
    ]
  }
}
```

### 3.3 Tool Descriptor
```jsonc
{
  "name": "read_file",
  "description": "Reads file contents.",
  "arguments_schema": {
    "type": "object",
    "properties": {
      "path": {"type": "string"}
    },
    "required": ["path"]
  },
  "permissions": ["read"],
  "source": "builtin|mcp",
  "capabilities": ["streamable"]
}
```

## 4. Extensibility Points

- **Command Plugins:** allow third parties to register new slash commands by providing metadata and handler functions.
- **Tool Providers:** pluggable registry where additional tools can be mounted dynamically (e.g., within `.aitestagent/extensions`).
- **Context Providers:** hook to inject custom context before each prompt (e.g., codebase summaries, issue tracker data).
- **UI Panels:** optional side panels for future features (e.g., conversation history, metrics) using `prompt_toolkit` containers.

## 5. Failure Modes & Mitigations

- **Blocked shell commands:** enforce sandbox rules, prompt user for confirmation, log decisions.
- **Tool errors:** capture stack trace, display user-friendly message, mark tool call as failed.
- **Large file ingestion:** warn and offer summarisation; support user override.
- **Network unavailability:** gracefully degrade features (e.g., MCP servers, web fetch) with status indicator.
- **Settings corruption:** maintain backup copies, provide `/settings reset` fallback.

## 6. Integration Checklist

- [ ] Define Pydantic models for settings and session logs.
- [ ] Implement CommandRouter with unit tests for parsing.
- [ ] Integrate prompt_toolkit and ensure compatibility with async event loop.
- [ ] Extend TestAutomationAgent for streaming output and cancellation.
- [ ] Implement MCP client (initially stubbed if necessary).
- [ ] Provide migration script for existing `.aitestagent/config.json`.

## 7. Next Steps

- Review blueprint with maintainers.
- Finalize dependency choices (`prompt_toolkit`, `rich` consoles, etc.).
- Proceed to Milestone 1 Task 3 (Dependencies & Environment Audit).
