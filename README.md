# superagent-from-scratch

**A ~1,000-line, zero-framework, teaching-first rebuild of a modern SuperAgent harness** — distilled from the heart of [bytedance/deer-flow](https://github.com/bytedance/deer-flow) (★76k), readable in one afternoon.

[中文版 README](README.zh-CN.md) · Teardown notes (Chinese) in [`notes/`](notes/)

> 🚧 **Work in progress** — slice S1 is being built in public (loop core done, real tools next). Follow along: each slice ships with passing offline tests and a teardown note.

## Why this exists

If you want to truly understand how a general-purpose agent works in 2026, the market leaves you stranded at both ends:

- **Flagship open-source projects are unreadable as textbooks.** deer-flow's backend is 185k lines; the agent core (~2,300 lines) is buried under a product shell — gateway, IM channels, multi-tenancy, persistence. You dig for three days before touching the heart.
- **Tutorials are too shallow.** Most stop at "call function calling once" and never reach the hard parts: context management, defensive middlewares, subagent isolation, goal loops — exactly what separates a production agent from a demo.
- **Frameworks hide the essence.** Mainstream implementations outsource the loop to LangChain/LangGraph. You see `create_agent(...)` — one line of black box — never the `messages → LLM → tools → append` cycle itself.

This repo rewrites deer-flow's ~2,300-line heart into **≤1,500 lines of dependency-free Python** (runtime deps: `anthropic` + `pyyaml`, nothing else), unfolded across five linear slices, each with offline tests and a why-first teardown note.

## Architecture

The 2026 consensus shape of a general-purpose agent — the same architecture as Claude Code, which deer-flow rewrote itself to match:

```
                ┌─────────────────────────────────────────────┐
                │              lead agent loop (S1)           │
                │  messages → LLM → tool_calls → run → append │
                │  terminate: natural close / turn fuse /     │
                │             interrupt signal                │
                └──────┬──────────────────┬───────────────────┘
                       │                  │
        ┌──────────────┴───────┐   ┌──────┴──────────────────────┐
        │ middleware pipeline  │   │ tools                       │
        │ (S2)                 │   │  bash / read_file /         │
        │  before_model        │   │  write_file (S1)            │
        │  after_model         │   │  task → subagent, fresh     │
        │  wrap_tool_call      │   │  context, returns only the  │
        │  · output budget     │   │  conclusion (S3)            │
        │  · error recovery    │   │  write_todos (S5)           │
        │  · summarization     │   │  ask_clarification (S5)     │
        └──────────────────────┘   └─────────────────────────────┘
                       │
        ┌──────────────┴──────────────────────────────┐
        │ skills (S4): SKILL.md discovery →           │
        │ metadata always-on, body loaded on /slash   │
        ├─────────────────────────────────────────────┤
        │ long-horizon (S5): plan externalized to     │
        │ todos + goal loop with re-run fuse + HITL   │
        └─────────────────────────────────────────────┘
```

## The five slices

Linear progression — each slice is a self-contained lesson with tests and a note:

| Slice | What you build | What you learn | Status |
|---|---|---|---|
| **S1** | The agent loop + LLM seam + 3 real tools | An agent is a while loop. The three (and only three) termination conditions. Why `tool_result` goes back as a `user` message. | 🔨 in progress |
| **S2** | Middleware protocol (`before_model` / `after_model` / `wrap_tool_call`) + 3 built-ins | Cross-cutting concerns decoupled from the loop — the real architecture of modern harnesses. Output budgets, error recovery, summarization. | ⬜ |
| **S3** | `task` tool + subagent delegation | Context isolation is the lifeline of long tasks. A subagent is not a new mechanism — it's the same loop, recursed, with a fresh context that returns only conclusions. | ⬜ |
| **S4** | Skills system (SKILL.md + slash activation) | The token economics of hot-pluggable capabilities: metadata is cheap (always-on), body is expensive (on-demand). | ⬜ |
| **S5** | `write_todos` + goal re-run loop + `ask_clarification` HITL | "Long-horizon" is not a longer model — it's a goal loop the harness wraps around the model, with fuses. Interrupt = a normal close that saves state. | ⬜ |

## deer-flow vs. this repo

Every cut is documented with an upgrade path (see `SPEC.md` → *product vs. teaching*). Cutting is the curriculum:

| Capability | deer-flow (production) | This repo (teaching) |
|---|---|---|
| Loop engine | LangChain `create_agent` (black box) | Hand-written `run()`, ~50 lines, fully visible |
| Context management | Summarization + DurableContext + TokenBudget + output caps | Summarization + ToolOutputBudget |
| Defense middlewares | LoopDetection / ReadBeforeWrite / DanglingToolCall / Safety… | ToolErrorHandling (each cut one = one exercise) |
| Multi-provider | ModelFactory + vLLM/thinking/vision adapters | `LLMClient` protocol: Anthropic + FakeLLM + CLI adapter |
| Tool sandboxing | Virtual path mapping + Docker sandbox | Bare subprocess, 60s timeout |
| Subagent executor | Thread pool + SSE event streams | Synchronous recursion into the same loop |
| Product shell | Gateway / IM channels / multi-tenant / tracing / TUI | None — that's 160k of the 185k lines, and it isn't the agent |

## Quick start

```bash
git clone https://github.com/libaoming/superagent-from-scratch.git
cd superagent-from-scratch
uv sync
uv run pytest -q   # fully offline — no API key, no network
```

All tests run against **recorded LLM fixtures** (`fixtures/fake_llm/*.json`): the single test seam is the `LLMClient` protocol; everything else — file system, subprocess — executes for real. No `mock.patch`, ever.

## Repo map

```
src/            the implementation (budget: ≤1,500 lines total)
tests/          one test suite per slice, all offline
fixtures/       recorded LLM response sequences + file-op sandbox
notes/          teardown notes (Chinese): how deer-flow does it →
                how this repo simplifies it → why → exercises
PRD.md          why this project exists, for whom
SPEC.md         every design decision with its "why" and deer-flow contrast
features.json   single source of truth for slice/feature status
```

## Teaching disciplines (enforced, not aspirational)

- **≤1,500 lines** in `src/` — exceeding it means replicating product features, not teaching the core. CI-checkable with `wc -l`.
- **Tests are offline** — a missing API key never blocks `pytest`.
- **Fixture-first** — fixtures are committed, reviewable data, not mocks.
- **No copied code** — deer-flow is read-only reference; everything is rewritten from understanding (clean MIT).
- **Every slice ships a note** — code without its teardown note doesn't count as done.

## License

[MIT](LICENSE)
