# Initial audit — GensIA — 20 October 2026

Status: RELEASE BLOCKED. Target review date: 22 October 2026, Africa/Maputo.

## Verified baseline

- Repository: https://github.com/Genseric0/GensIA
- Default branch: main; commit `206f4d1798d516deccb3268938777b1348cfb85b`, v0.34.0.
- Branch for this work: `release/hardening-2026-10-22`.
- No AGENTS.md found. No workflows, open PRs or open issues returned on 20 October.
- Historical local v0.43–0.60 reports are not the current remote implementation.
  Workspace maintenance removed their scratch files; Library search found only an
  older v0.18 ZIP. Work proceeds from the verified remote rather than treating
  historical test counts or missing code as current evidence.

## Architecture and inventory

Python standard-library CLI (`gensia/__main__.py`, `cli.py`) orchestrates explicit
tools, memory, local Ollama, voice adapters, documents and four role-based agents.
SQLite stores explicit notes; logical JSON backup and exclusive new-file restore
already exist. FastAPI/Uvicorn expose loopback diagnostics; panel.html/css/js is a
token-authenticated diagnostics UI. The remote has no chat page or chat endpoint.
PDF has a supervised process, timeouts and Linux resource limits. Whisper/Piper,
audio hardware, Ollama weights and third-party services are optional integrations.

Directories reviewed: gensia/, gensia/web/, tests/, scripts/, docs/, requirements
and repository configuration. Existing tests use unittest and Node's test runner.
No financial business domain, customer billing or stock model exists here.

## Execution before implementation

Environment: Linux, Python 3.12.14, Node 24.19.0. Global pypdf6.10.0 differs from
requirements-documents6.20.1; FastAPI/Uvicorn/httpx/Bandit are absent. Node
Playwright1.62.1 is available but its Chromium executable is absent.

`python -B -m unittest discover -s tests -q`: 277 total,250 passed,27 skipped,
0 failures,10.019s. These omissions prevent full API/PDF/real-HTTP approval.

`GENSIA_PYTHON=python node --test tests/panel.test.cjs tests/panel_browser_runner.test.cjs tests/catalog_visual.test.cjs`:
34 total,33 passed,1 failed,0 skipped,0.134s. Helper failed to start its API because
the interpreter lacks optional API dependencies. This is an execution blocker,
not evidence of an application security defect. Full baseline will be repeated
in an isolated environment with required extras.

Controlled baseline completed on 21 October in a detached worktree at the same
commit, using the new isolated environment: 277 Python tests passed, zero skipped,
11.376s, with GENSIA_TEST_REAL_HTTP=1. All 34 original Node tests passed with
GENSIA_PYTHON set to that interpreter, zero skipped,0.637s. This establishes the
original application baseline independently of the corrected working tree.

## Reproduced priorities

| ID | Priority | Trigger and observed result | Planned correction |
| --- | --- | --- | --- |
| AUTH-001 | P1 | approved='false' opens an application and deletes a note; non-True approvals reach VirusTotal/CISA openers | Require exact True before any side effect |
| AUDIT-001 | P1 | AppLauncher calls runner before audit; audit failure occurs after application opened | Durable intent before runner; truthful final-audit failure outcome |
| PRIV-001 | P1 | Ollama reply sends chat prompt without checking local model metadata; local_only=True is asserted | Central metadata gate; block remote/unconfirmed models before content |
| TERM-001 | P1 | Ollama response with OSC52/ESC/BEL reaches printed output | Strict response schema/JSON/Unicode and terminal-control validation |
| DATA-001 | P1 | New memory DB observed0644 with permissive umask; hardlink write changes original | Exclusive0600 creation, regular/single-link checks |
| DATA-002 | P1 | get SELECT* returns added column and1MiB value; backup NUL value exports shortened prefix | Fixed bounded projections, strict types/Unicode/date, duplicate checks |
| UX-001 | P1 | Browser has diagnostics only; essential requested chat flow unavailable | Build actual local chat on existing FastAPI/Ollama stack |
| BUILD-001 | P1 | No installable package or CI; optional tests can omit essential coverage | Package/locked requirements and mandatory CI gates |
| INPUT-001 | P2 | list(True,False) accepted; list('1') raises TypeError; invalid Unicode creates empty DB | Validate types/ranges/UTF8 before disk access |
| VISUAL-001 | P2 | No real browser screenshots or responsive-layout evidence | Install controlled browser if accessible; capture running synthetic demo |
| RELEASE-001 | P1 release gate | No real weights/hardware/Windows/client isolation evidence | Document remaining gates; do not approve commercial/shared deployment |

Security and data reproductions used temporary synthetic fixtures and mocked
network/process boundaries, never real accounts or external targets. No P0 has
been established by this initial inspection. This is not a complete ASVS assessment.

## Scope and sequence

1. Fix authorization, audit ordering, local inference gate and memory integrity.
2. Restore a usable chat interface with bounded/authenticated API operations.
3. Execute unit/integration/real-loopback/browser and database recovery checks.
4. Add least-privilege CI, packaging, dependency/secret scans and release evidence.
5. Publish reviewed changes to the development branch and open a PR; inspect CI.

P3 cosmetics and new orchestration dependencies are deferred. Goose is not
installed/configured here; actual Codex specialist agents perform the review.
The previously cancelled hourly automation remains disabled. A CI runner executes
only committed workflow events; this session does not establish continuous AI work.

Reference: OWASP ASVS5.0.0, https://owasp.org/projects/asvs (verified20 October).
Detailed control applicability and outcomes belong in SECURITY_AUDIT.md.
