# Interactive Mode – Requirements Capture (Milestone 1, Task 1)

This document records the detailed requirements for delivering an interactive experience comparable to the Google Gemini CLI. It addresses the following subtasks:

1. Catalogue Gemini CLI user flows.
2. Produce a feature parity matrix (mandatory vs. optional).
3. Highlight constraints imposed by the current `ai-test-agent` architecture.

## 1. Gemini CLI User Flows

### 1.1 Session Lifecycle
- **Launch session:** start CLI (`gemini`), load settings, authenticate, detect workspace trust level.
- **Prompt loop:** accept natural language prompts, stream responses, maintain conversation context.
- **Exit:** support exit keywords (`exit`, `quit`), keyboard interrupts, optional checkpoint confirmation.

### 1.2 Prompt Input Modes
- **Plain prompts:** default mode sending text directly to the model.
- **Slash commands (`/command`):** meta-operations controlling session state (help, history, compression, etc.).
- **At commands (`@path`):** embed files or directories into prompts with git-aware filtering.
- **Bang commands (`!command` / shell mode):** execute shell commands inline or enter persistent shell passthrough.
- **Mention commands (`@alias prompt`):** route to specific MCP servers or extensions (e.g., `@github`).

### 1.3 Slash Command Families
- **Help & docs:** `/help`, `/bug`, `/extensions`, `/commands`.
- **Session management:** `/chat save|resume|list|delete|share`, `/history`, `/clear`, `/compress`.
- **Workspace control:** `/directory add|show`, `/context`, `/init`, `/settings`.
- **Mode toggles:** `/mode vim`, `/mode default`, keyboard shortcut announcements.
- **Tooling & MCP:** `/mcp list|desc|schema|auth`, `/tools`.
- **Clipboard & editor:** `/copy`, `/editor`.

### 1.4 File & Context Handling
- **File ingestion:** expand `@file`, multiple paths, range specifiers, large file truncation warnings.
- **Directory ingestion:** recursive read with ignore patterns, progress updates.
- **Context files:** auto-load `GEMINI.md` (project instructions), allow overrides.
- **Checkpointing:** automatic saves before destructive operations; manual restore via `/chat`.

### 1.5 Tool Execution & Visualization
- **Built-in tools:** read/write files, list directories, run shell commands, fetch web content, Google Search grounding.
- **Tool cards:** display tool name, arguments, success/failure, latency.
- **Chained actions:** model may call multiple tools sequentially, showing observations.
- **MCP integrations:** discoverable tools registered via MCP servers; per-tool auth workflows.

### 1.6 Shell Mode
- **Inline commands:** `!ls` executes once and returns to prompt.
- **Persistent shell:** entering `!` toggles shell prompt until exited.
- **Context markers:** distinct prompt style, environment variable (e.g., `GEMINI_CLI=1`), sanitized output handling.

### 1.7 Settings & Profiles
- **Configuration hierarchy:** global `~/.gemini/settings.json`, project overrides, environment flags.
- **Trusted folders / sandbox profiles:** warnings or restrictions for untrusted directories.
- **Authentication flows:** storing & refreshing tokens, surfacing status in UI.

### 1.8 Personalization & Extensibility
- **Custom commands:** user-defined shortcuts or macros.
- **Extensions:** plugin architecture for additional commands/tools.
- **Telemetry opt-in/out:** record usage metrics, respect privacy settings.

### 1.9 Accessibility & UX Enhancements
- **Keyboard shortcuts:** e.g. Ctrl+L (clear), Ctrl+Z (undo), Ctrl+Shift+Z (redo).
- **Status footer:** display current mode, model, latency, sandbox state.
- **Streaming responses:** incremental output, cancellation support.

## 2. Feature Parity Matrix

| Feature | Description | Parity Tier | Notes |
| --- | --- | --- | --- |
| Basic prompt-response loop | Streamed model interaction with history | **Must Have** | Foundation of interactive mode |
| Slash command framework | `/help`, `/chat`, `/clear`, `/copy`, `/compress` | **Must Have** | Gemini CLI relies heavily on slash commands |
| Chat checkpointing | Save, resume, list, delete, share conversation states | **Must Have** | Required for long-running sessions |
| At command file injection | Embed files/directories with git-aware filtering | **Must Have** | Critical for code understanding workflows |
| Bang shell commands | `!cmd` and shell mode toggle | **Must Have** | Core developer expectation |
| Tool call visualization | Structured display of LLM tool usage | **Must Have** | Essential to trust automation |
| Built-in tools parity | File IO, shell, web fetch, search | **Must Have** | Aligns with Gemini CLI default toolkit |
| MCP server integration | Discover/register external tools | **Must Have** | Gemini CLI promotes MCP as extension system |
| Settings hierarchy | Global + project + session overrides | **Must Have** | Needed for enterprise readiness |
| Trusted folder policies | Sandbox profiles, warnings | **Must Have** | Aligns with Gemini security posture |
| Vim input mode | `/mode vim` + status indicator | **Should Have** | Common developer feature; promote parity |
| Custom commands | User-defined shortcuts/macros | **Should Have** | Enhances personalization |
| Context file (`AITESTAGENT.md`) | Auto-load project-specific instructions | **Should Have** | Equivalent to `GEMINI.md` |
| Telemetry hooks | Optional analytics with opt-in | **Should Have** | Useful for future improvements |
| GUI/editor launch | `/editor` to open configured editor | **Nice to Have** | Dependent on system capabilities |
| Search grounding | Google-like search integration | **Nice to Have** | Requires external API support |
| GitHub/Slack extensions | Sample MCP integrations | **Nice to Have** | Demonstrates extensibility |
| Token accounting utilities | `/tokens`, `/compress` heuristics | **Nice to Have** | Helpful but not critical |

## 3. Existing System Constraints

### 3.1 LLM Integration
- **Ollama dependency:** current agent instantiates `Ollama(model=settings.llm_model_name)` (`agent.py`) limiting model choices without additional provider support.
- **LangGraph orchestration:** agent uses LangGraph state machines; interactive mode must either reuse or wrap this flow for tool invocation consistency.

### 3.2 Async & Concurrency Model
- **Async-heavy components:** file tools, test runner, and agent methods rely on `asyncio`; REPL must manage event loop carefully (e.g., use `asyncio.run`, `prompt_toolkit` async interface).
- **Test runner side-effects:** `TestEnvironment` manipulates virtualenvs and installs dependencies; interactive actions must warn before destructive tasks or require confirmation.

### 3.3 File System & Sandbox
- **Workspace-write sandbox:** CLI operates relative to configured project root with apply_patch/edit restrictions; shell mode needs guardrails to respect sandbox settings.
- **Manifest resolution:** `resolve_project_context` enforces path normalization; interactive mode must honour manifest overrides.

### 3.4 Configuration & Settings
- **Pydantic `Settings`:** global config currently tied to environment variables and manifest; new interactive settings must integrate without breaking existing CLI commands.
- **Session persistence:** existing `SessionManager` stores minimal snippets; needs extension for checkpoints, tool history, and multi-thread support.

### 3.5 Tooling & Extensibility
- **Tool registry:** tools currently defined in `agent/tools.py`; interactive mode should expose this registry while enabling additional tool types (web fetch, search).
- **MCP absence:** no current MCP infrastructure; implementing parity requires new client, protocol handling, and settings schema.

### 3.6 User Experience Considerations
- **Terminal UI:** no existing dependency on `prompt_toolkit`; adopting it introduces new dependency and requires compatibility audits (Python 3.12 target).
- **Cross-platform support:** shell mode must work on POSIX & Windows; consider differences in environment variables, clipboard access, editor launching.
- **Telemetry/legal:** project currently lacks telemetry; any analytics must follow licensing/privacy policies.

### 3.7 Resource Constraints
- **Performance:** parsing large repositories via tree-sitter is expensive; need caching strategy for repeated file injections.
- **Testing:** limited automated coverage for interactive workflows; plan must include integration test harness.

---

**Next actions:** review requirements with stakeholders, validate parity priorities, and proceed to Milestone 1 Task 2 (technical design blueprint).
