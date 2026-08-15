# AI Agent Design

## 1. Philosophy

AI is an enhancement layer, never a dependency. Everything the platform must do —
sync, execution, ingestion, metrics, coverage, defects, sprint metrics, dashboard,
PDF, reports, notifications — is deterministic and works with `LLM_PROVIDER=none`.
AI is used for reasoning over deterministic facts: AC interpretation, test-gap
detection, test generation, failure explanation, risk analysis, executive
summaries and recommendations.

## 2. Provider Interface

```python
class LLMProvider(Protocol):
    async def chat(self, *, messages, model=None, temperature=None,
                   response_format=None) -> str: ...
    async def structured(self, *, messages, schema: type[BaseModel],
                         model=None) -> BaseModel: ...
    async def analyze_story(self, story, existing_tests, history) -> StoryAnalysis: ...
    async def identify_test_gaps(self, analysis_input) -> GapAnalysis: ...
    async def generate_test_cases(self, request) -> GeneratedTests: ...
    async def summarize_test_results(self, data) -> str: ...
    async def explain_failure(self, result) -> str: ...
    async def executive_summary(self, metrics) -> str: ...
```

`structured()` guarantees schema-conforming output: the provider parses JSON
responses and validates against the Pydantic schema, retrying once on failure.
Whatever the provider returns is **validated again** by the calling service before
any database write. The LLM never writes to the database directly.

## 3. Providers

| Provider | Notes |
|---|---|
| `HeuristicLLMProvider` | Deterministic, rule-based fallback. Never returns `None`; always returns schema-valid objects. This is the default. |
| `OpenAICompatibleProvider` | Chat Completions API via `LLM_BASE_URL`. Covers OpenAI, OpenCode-compatible endpoints, Ollama, LM Studio, vLLM. |
| `AnthropicProvider` | Anthropic Messages API. |

Selection: `LLM_PROVIDER in {none, heuristic, openai, openai_compatible,
anthropic, opencode, local}`; `opencode`, `openai` and `local` map to
`OpenAICompatibleProvider` with different defaults for `LLM_BASE_URL`/model.
`LLM_MODEL` and `LLM_BASE_URL` are never hard-coded.

## 4. Test-Matrix Analysis Workflow (`POST /test-manager/sync-test-matrix`)

1. Load work item + ACs + existing links + test history + recent PRs (deterministic).
2. Build an `analysis_input` (tokens trimmed, PII filtered).
3. Call `analyze_story` → validate → get `StoryAnalysis`:
   - `is_new_functionality: bool`
   - `ac_coverage: [{criterion, has_test, reuse_candidates, suggested_new_scenarios}]`
   - `reuse: [existing test keys]`, `new_tests: [proposed {title, framework}]`
   - `redundant: [keys]`, `coverage_pct`, `status: COVERED|PARTIALLY_COVERED|NOT_COVERED|REVIEW_REQUIRED`
4. Persist `test_matrix_analyses` row (append-only; latest per story wins for UI).
5. Create/update `acceptance_criteria` rows (status = covered if a link exists).
6. Persist proposed new test cases as `test_generation_candidates` (status
   `proposed`) — **not** active test cases. Human approves in UI before any test
   is created.
7. Optional: add structured comment to Azure story (config `AZURE_COMMENT_ON_ANALYSIS`).
8. Emit `coverage_gap` notification if missing ACs exist.

## 5. Test Generation Workflow (`POST /test-manager/create-test-cases`)

Requires: a completed analysis with approved candidates.

1. Deterministic steps: create branch `test/story-<id>-generated-tests` in repo.
2. `generate_test_cases` → validate → map proposals to framework (api/ui/both).
3. Write implementation files into the correct framework checkout.
4. Run the affected tests (framework runner).
5. Parse results; if green, commit + push; create Azure PR.
6. Return `{branch, tests_created, test_execution, pull_request_url, status: REVIEW_REQUIRED}`.
7. **Never merges.** PR status human-controlled.

In `APP_ENV != demo`, generation requires `GIT_REMOTE_URL`, `AZURE_REPO_NAME` and
a git credential mechanism. In demo mode a local git repo is used so the workflow
is demonstrable without a real remote.

## 6. Failure Explanation

`explain_failure(result, recent_commits, related_results)` produces a short,
evidence-based explanation and suggested next steps. Exposed in the test-results
detail and in reports as "notable failures".

## 7. Guardrails

- Every LLM call is wrapped in a timeout (`LLM_TIMEOUT_SECONDS`, default 60).
- Output schema validation on every call; retry once; fall back to heuristic on
  final failure (logged).
- Tokens/context trimmed; work-item descriptions truncated.
- Rate limiting and concurrency limits on jobs using LLM.
- Model name, prompt version and validation result recorded in the analysis row
  for auditability.
- Prompt injection mitigation: system prompt instructs the model to treat
  work-item content as untrusted data, not instructions.
