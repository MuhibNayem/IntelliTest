# Interactive Mode – Dependencies & Environment Audit (Milestone 1, Task 3)

This audit evaluates third-party libraries, system prerequisites, storage plans, and configuration impacts required to deliver the Gemini-like interactive mode.

## 1. Runtime & Library Dependencies

| Dependency | Purpose | Evaluation | Decision/Action |
| --- | --- | --- | --- |
| `prompt_toolkit` (>=3.0.48) | Advanced REPL UI (key bindings, history, layout) | Already listed in `pyproject.toml` as runtime dependency. Need to verify version sufficiency for streaming + async integration. | Proceed; confirm compatibility with Python 3.12 and Windows terminals. |
| `rich` | Enhanced console rendering, progress spinners | Already in project; can reuse for tool call rendering/log panels. | No change needed; define consistent styling across interactive mode. |
| `pyperclip` / platform clipboard utilities | Implement `/copy` command | Optional; Gemini CLI requires platform-specific tools (pbcopy/xclip/clip). Need detection logic and instructions. | Add optional dependency or provide warnings when absent. |
| `watchdog` (optional) | Monitor file changes for auto-refresh context | Could improve UX but not mandatory; evaluate later. | Defer unless required by design decisions. |
| `aiohttp` / `httpx` | Web fetch/Search tool implementation | Not currently required; choose when implementing web tools. | Document as future dependency (Milestone 5). |
| MCP SDK (`mcp` or custom implementation) | Model Context Protocol client | No Python reference implementation identified. May need to implement minimal MCP client or adapt open-source library if available. | Research existing Python MCP libraries; plan to build internal client if none stable. |
| `pyyaml` (optional) | Settings file serialization | Current project uses JSON; YAML optional. | Stick to JSON for now to avoid new deps. |
| `msgpack` / `orjson` (optional) | Efficient session log storage | Consider for large conversations; optional optimization. | Evaluate during implementation; keep optional. |

### 1.1 Python Version
- Target Python 3.12 per `pyproject.toml`.
- Ensure all chosen libraries support 3.12.
- Validate Windows support for prompt_toolkit features.

## 2. System Requirements & External Tools

| Requirement | Notes |
| --- | --- |
| Shell commands | On Unix: `/bin/bash`; On Windows: PowerShell (`pwsh` or `powershell.exe`). Need detection logic. |
| Clipboard tools | macOS: `pbcopy`; Linux: `xclip` or `xsel`; Windows: `clip`. Provide instructions when missing. |
| Editors for `/editor` command | Detect `$EDITOR` / `$VISUAL`; fallback to platform defaults (vim/nano/notepad). |
| Network access | Required for web fetch, search grounding, MCP servers. Provide clear messaging when network is restricted. |
| File permissions | Must handle sandbox policies (workspace-write). Restrict destructive operations when necessary. |

## 3. Storage Layout

- **Global settings**: `~/.aitestagent/settings.json`
  - Store interactive preferences (`default_mode`, trusted folders, MCP servers).
  - Provide migration script to create file if missing.
- **Project settings**: `<project>/.aitestagent/settings.json`
  - Override subset of global settings.
  - Commit guidelines for shared configurations.
- **Session data**: `~/.aitestagent/tmp/<project_hash>/`
  - `session.log`: conversation history (JSON/MsgPack).
  - `checkpoints/<tag>.json`: captured snapshots.
  - `attachments/`: stored external file digests if needed.
- **Cache directory**: optionally store summarised contexts, MCP schemas.
  - Ensure cleanup strategy (LRU or manual `/cache clear` command).

## 4. Configuration Impact

- Extend existing `Settings` model:
  - Add `interactive` section (Pydantic nested model).
  - Provide environment variable overrides (e.g., `AITEST_INTERACTIVE_MODE=vim`).
  - Ensure backward compatibility with CLI commands using `settings`.
- Update `resolve_project_context`:
  - Load new settings paths in addition to manifest.
  - Validate relative paths relative to project root.
- Provide migration utilities:
  - CLI command `/settings migrate` or `ai-test-agent settings migrate`.
  - Document new configuration files in `docs/CLI_REFERENCE.md`.

## 5. Security & Sandbox Considerations

- Shell execution must respect sandbox:
  - When sandbox=workspace-write, restrict `!` commands to project workspace; prompt for confirmation otherwise.
  - For read-only sandbox, block shell writes and offer override instructions.
- Tool permission levels:
  - Annotate tools with required permissions (read/write/network).
  - Add enforcement layer before execution (ask user to allow).
- Trusted folder policy:
  - Maintain list in settings; warn when launching in untrusted directories.
  - Provide `/trust add <path>` command to persist trust.
- Credential handling:
  - Ensure tokens (LLM, MCP) are stored securely in settings (support keychain integration if needed).

## 6. Logging & Telemetry

- Logging:
  - Use `logging` module with interactive-specific logger.
  - Provide option to create detailed logs in `~/.aitestagent/logs/interactive.log`.
- Telemetry (optional):
  - If added, ensure opt-in setting; default to disabled.
  - Sanitize any sensitive data (file paths, prompts).

## 7. Testing & Tooling Implications

- Unit tests require ability to simulate prompt_toolkit input:
  - Use `prompt_toolkit` testing helpers or custom input feeders.
- Integration tests:
  - CLI harness capable of programmatically interacting with REPL (pexpect or similar).
- CI environment:
  - Ensure tests skip features needing unsupported system utilities (e.g., clipboard) or mock them.

## 8. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| prompt_toolkit async conflicts | Use documented asyncio integration pattern (`Application.run_async`). Write regression tests. |
| MCP client complexity | Phase delivery: start with stub registry, add protocol support incrementally. |
| Platform inconsistencies | Build cross-platform abstraction for shell execution & clipboard. Add docs per OS. |
| Settings sprawl | Define schema early, enforce validation, supply defaults. |
| Storage growth | Provide housekeeping commands to clean caches/checkpoints. |

---

**Next actions:** begin Milestone 2 implementation (Session Manager enhancements and REPL scaffolding) using the requirements and design captured in Tasks 1.1–1.3.
