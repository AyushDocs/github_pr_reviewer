# GitHub PR Reviewer

**Multi-agentic, multi-RAG, graph-based PR review engine** — parallel code + security reviewers powered by hybrid search retrieval, guarded by jailbreak detection, hallucination validation, and quality gates, with configurable CI/CD deployment and per-repo policy.

## Architecture

```
fetch → jailbreak_gate ──[clean]──→ pr_size_gate ──[ok]──→ review ────→ summarize ──→ evaluate ──→ validity_gate ──[pass]──→ human_gate ──→ comment ──→ END
                            │                              │                 │                         │                                       │
                            │                           [too_large]       (parallel via            [block]                              (interrupt
                            │                              │                ThreadPoolExecutor)       │                                      for CLI)
                            │                              ↓                                         ↓
                            └──[injection]──→ flag_injection ──→ END    flag_blocked ──→ END
```

### 11 Graph Nodes

| Node | Role | I/O |
|------|------|-----|
| `fetch` | Fetch PR files from GitHub API | Returns `files`, `diffs` or `error` |
| `jailbreak_gate` | Regex-based prompt injection scan | Sets `injection_detected`, routes to `flag_injection` or `pr_size_gate` |
| `pr_size_gate` | Checks PR against file count and patch size limits | Sets `pr_too_large`, routes to `flag_blocked` or `review` |
| `review` | Parallel code review + security review via LLM | Runs `review_chain` + `security_chain` per file via `ThreadPoolExecutor` |
| `summarize` | Generates PR summary via LLM | Skips LLM call if no reviews produced |
| `evaluate` | Quality scoring + hallucination detection | `quality_score` (0-100), `hallucination_flags` |
| `validity_gate` | Blocks on: hallucination flags, quality <60, injection | Sets `block_review`, routes to `flag_blocked` or `human_gate` |
| `human_gate` | Interrupt point for CLI approval | LangGraph `interrupt_before` |
| `flag_injection` | Posts injection warning comment | Skips review entirely |
| `flag_blocked` | Posts "review skipped" notice | When quality/hallucination checks fail |
| `comment` | Posts summary + inline file comments | GitHub issue comment + review comments |

### Reviewer Agents (Parallel)

- **Code Reviewer** (`review_chain`): General code quality, best practices, maintainability
- **Security Reviewer** (`security_chain`): OWASP Top 10 vulnerabilities (SQL injection, XSS, command injection, hardcoded secrets, etc.)

Both use **RAG-augmented prompting** — the LLM receives relevant knowledge base entries alongside the diff.

## Hybrid Search Retrieval (BM25 + Dense)

The knowledge base is searched using a hybrid approach:

- **BM25** (keyword): `rank-bm25` with tokenized diff text (weight 0.3)
- **Dense** (semantic): `nvidia/nv-embed-v1` via `NVIDIAEmbeddings` (dim 4096) (weight 0.7)
- **Cached embeddings**: Computed once, persisted in `.chroma/` directory (or fallback JSON cache)
- **Metadata filtering**: Filter by severity, version, popularity at query time

### Knowledge Base

- `code_review_bp.py` — 20 ranked code review bad practices (CR-001 to CR-020)
- `security_bp.py` — 20 ranked OWASP-style security entries (SEC-001 to SEC-020)
- Each entry: `id`, `title`, `severity`, `version`, `popularity`, `description`, `bad_pattern`, `good_pattern`, `suggested_fix`, `keywords`

## Safety Guards (Phase 1)

- **Jailbreak detection**: Regex patterns for prompt injection (`ignore previous instructions`, `system prompt`, base64 payloads, suspicious comments). Routes to `flag_injection` node.
- **Hallucination detection**: Pattern-matching against diff content (flags generic "potential SQL injection" when no SQL code exists)
- **Quality scoring**: 0-100 with deductions for unparseable JSON, invalid severity, vague explanations, too many CRITICAL findings
- **Validity gate**: Blocks review posting if hallucination detected, quality <60, or injection found

## Fallback LLM Provider

If the primary NVIDIA AI Endpoints model returns a `ConnectionError`, the chain automatically retries with a fallback LLM:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_FALLBACK_API_KEY` | — | API key for fallback provider |
| `AI_FALLBACK_MODEL` | `google/gemma-2-2b-it` | Model name for fallback |

The fallback is optional — if `AI_FALLBACK_API_KEY` is not set, the chain raises `ConnectionError` and the graph's global `RetryPolicy` handles it.

## Graceful Degradation

When all LLM calls for a PR's diffs fail (or the PR is too large):

- `review_degraded=True` is set in the graph state
- The summary reads **"Review Unavailable — LLM API unavailable"**
- Inline file comments are skipped
- A degraded notice is posted on the PR instead
- The `$GITHUB_STEP_SUMMARY` report shows **Degraded: Yes**

## PR Size Limits

To bound cost and latency, PRs exceeding configurable limits are skipped:

| Variable | Default | Description |
|----------|---------|-------------|
| `PR_MAX_FILES` | `50` | Maximum number of files before skipping |
| `PR_MAX_PATCH_SIZE` | `500000` | Maximum total patch bytes before skipping |

When skipped, the graph posts a "Review skipped: PR too large" comment and ends.

## LLM Concurrency & Rate Limiting

The system uses a `threading.Semaphore` to cap concurrent NVIDIA API calls — essential for avoiding 429 rate limits:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_LLM` | `5` | Max concurrent LLM invocations across all file reviews |
| `MAX_DIFF_CHARS` | `15000` | Max characters per diff sent to the LLM (truncated with warning marker) |

## Diff Pre-processing

Before sending a diff to the LLM, the system:

1. **Strips excess context lines** — only the first 3 unchanged lines around each hunk are kept (reduces token usage ~40%)
2. **Truncates oversized diffs** — diffs longer than `MAX_DIFF_CHARS` are split into head/tail with a truncation notice
3. **Preserves `+`/`-` lines** — all added and removed lines are kept in full

## Cost & Token Tracking

Every LLM invocation records prompt and completion tokens from the API response metadata. These are accumulated across all parallel calls and reported:

- **Prompt tokens**: Total input tokens sent to the LLM
- **Completion tokens**: Total output tokens generated
- **Total tokens**: Sum of both
- **Estimated cost**: Computed using NVIDIA AI Endpoints pricing (default $0.10/1M input + $0.10/1M output)

These metrics appear in:
- The `$GITHUB_STEP_SUMMARY` report in CI
- Log output in CLI mode
- LangSmith traces (automatically via `@traceable`)

## Prompt Versioning

Each prompt template includes a `PROMPT_VERSION` constant (e.g. `"1.1"`) embedded in the system instruction sent to the LLM. This allows:

- Identifying which prompt version produced any given review
- A/B testing prompt iterations
- Adding the version to LangSmith trace metadata for debugging

## LangGraph Runtime Configuration

- **RetryPolicy**: 3 attempts globally (1s-30s exponential backoff, jitter). `review` node: 2 attempts only for `ConnectionError`.
- **CachePolicy**: 30-minute TTL for deterministic nodes (evaluate, validity gate)
- **Timeout**: 300s hard cap on review batch (`as_completed(timeout=300)`)
- **Checkpointer**: `MemorySaver` for CLI with `interrupt_before=["human_gate"]`
- **Two compiled variants**: `app` (with checkpointer + interrupt) for CLI, `app_auto` (no checkpointer) for CI

## CI / GitHub Actions

- Triggered on `pull_request` (opened, synchronized)
- Runs full pipeline: fetch → review → evaluate → comment on PR
- Review results cached by diff hash (`actions/cache`) — same diff reuses cached result
- Posts summary comment + batch file-level review comments via `create_review`
- Writes structured `$GITHUB_STEP_SUMMARY` report with duration, file count, quality score, degradation status
- Email notification via SMTP (Gmail App Password) on completion
- Falls back to a PR comment if SMTP is configured but sending fails
- Requires `LANGSMITH_API_KEY` — CI fails if not set (ensures every review is traced)

## Evaluation Harness (Phase 3)

- **9 ground-truth test cases**: SQL injection, hardcoded secrets, command injection, path traversal, bare except, eval usage, MD5 hashing, multi-file PR, clean PR
- **Runner**: Runs the graph against each case, parses findings, compares against expected
- **Metrics**: Precision, recall, F1 score

## Quick Start

```bash
# Install
pip install -e . "langgraph-cli[inmem]"

# Set up .env
cp .env.example .env
# Edit .env: AI_API_KEY, GITHUB_TOKEN, LANGSMITH_API_KEY (optional)

# Run CLI
python -m src.agent.graph

# Run tests
pytest tests/ -v

# Run evaluation harness
python -m tests.harness.runner

# Start API server
uvicorn api.server:app --reload
```

## Per-Repo Configuration

Place a `review_config.json` in the root of your repository to override global defaults:

```json
{
  "min_severity": "MEDIUM",
  "skip_files": ["*.generated.py", "vendor/*", "third_party/*"],
  "max_files": 30,
  "max_patch_size": 300000
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `min_severity` | `LOW` | Minimum severity to report (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `skip_files` | `[]` | Glob patterns for files to skip during review |
| `max_files` | `50` | Max files before PR is skipped (env `PR_MAX_FILES` takes priority) |
| `max_patch_size` | `500000` | Max total patch bytes (env `PR_MAX_PATCH_SIZE` takes priority) |

Env vars always take precedence over the config file.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AI_API_KEY` | Yes | — | NVIDIA AI Endpoints API key |
| `GITHUB_TOKEN` | Yes | — | GitHub personal access token |
| `AI_MODEL` | No | `google/gemma-2-2b-it` | LLM model |
| `AI_EMBEDDING_MODEL` | No | `nvidia/nv-embed-v1` | Embedding model |
| `AI_TEMPERATURE` | No | `0.2` | LLM temperature |
| `AI_TOP_P` | No | `1.0` | LLM top-p sampling |
| `AI_MAX_TOKENS` | No | `1024` | Max completion tokens |
| `AI_FALLBACK_API_KEY` | No | — | Fallback LLM API key (on API error) |
| `AI_FALLBACK_MODEL` | No | `google/gemma-2-2b-it` | Fallback LLM model |
| `MAX_CONCURRENT_LLM` | No | `5` | Max concurrent NVIDIA API calls |
| `MAX_DIFF_CHARS` | No | `15000` | Max diff chars sent to LLM per file |
| `AI_FALLBACK_MODEL` | No | `google/gemma-2-2b-it` | Fallback LLM model |
| `LANGSMITH_API_KEY` | No | — | LangSmith tracing |
| `PR_MAX_FILES` | No | `50` | Max files before PR is skipped as too large |
| `PR_MAX_PATCH_SIZE` | No | `500000` | Max total patch bytes before PR is skipped |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server host |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASS` | No | — | SMTP password (e.g. Gmail App Password) |
| `SMTP_FROM` | No | `pr-reviewer@example.com` | SMTP sender email |
| `REVIEW_LOG_LEVEL` | No | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |

## Graph Flow Diagram

```
                    ┌──────────┐
                    │  fetch   │
                    └────┬─────┘
                         │
                    ┌────▼──────┐
                    │jailbreak  │
                    │   gate    │
                    └────┬──────┘
                         │
               ┌─────────┼──────────┐
               │ clean            injection
               │                   │
          ┌────▼────────┐   ┌─────▼──────────┐
          │pr_size_gate │   │ flag_injection  │──→ END
          └────┬────────┘   └────────────────┘
               │
         ┌─────┼─────┐
         │ ok      too_large
         │          │
    ┌────▼─────┐ ┌──▼───────────┐
    │  review  │ │ flag_blocked │──→ END
    │(parallel)│ └──────────────┘
    └────┬─────┘
         │
    ┌────▼────────┐
    │  summarize  │
    └────┬────────┘
         │
    ┌────▼────────┐
    │  evaluate   │
    └────┬────────┘
         │
    ┌────▼──────────┐
    │ validity_gate │
    └────┬──────────┘
         │
   ┌─────┼───────┐
   │ pass       block
   │             │
  ┌▼──────┐  ┌──▼───────────┐
  │human  │  │ flag_blocked │──→ END
  │ gate  │  └──────────────┘
  │(intr.)│
  └──┬────┘
     │
  ┌──▼───────┐
  │ comment  │──→ END
  └──────────┘
```
