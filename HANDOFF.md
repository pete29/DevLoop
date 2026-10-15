# HumanInTheLoop: handoff

Read this before you touch the code. It covers what the project is, what changed in the
session of 14–15 October 2026, what is decided, what is still open, and the traps already found.
`docs/ARCHITECTURE.md`, `docs/SECURITY.md` and `docs/CONFIGURATION.md` are current and go
deeper. This file is the map.

---

## 1. What this is

**DevLoop**  is an **AI software factory with
human-in-the-loop governance**. A requirement goes in; AI agents plan it, write it, review it,
test it; a human approves every change; git and GitHub carry it to a pull request; a human
merges.

```text
Requirement (manual or GitHub issue)
  → Planner (Opus)              tasks + dependencies, validated in code
  → Step 0: environment         scaffolding, npm install, scaffolding commit (deterministic, buttons)
  → per task, on the plan's branch:
      Developer (Sonnet)        one call per file
      Free checks               structural validator + tsc (no model)
      Architect (Opus)          only reviews code that passed the free checks
      QA (Sonnet)               one Vitest suite per source file
      Compile + tests           real tsc, real Vitest
  → Human: accept / reject      accept = commit on the plan's branch; reject = files undone
  → Push → PR (one per plan, description rebuilt on every push)
  → Human merges on GitHub → "Check the PR" → requirement DELIVERED
```

**The core rule:** facts belong to code, reasoning belongs to AI. Anything that can be decided
mechanically (does a file exist, does an import resolve, does it compile, is a branch behind
origin, which file exports a symbol) is decided in code and never asked of a model. Every
pipeline stage is either deterministic or AI, never both.

**Stack of the tool:** Python 3.13, Streamlit UI (`app.py`), SQLite (`human_in_the_loop.db`),
Anthropic SDK. **Stack it generates:** TypeScript + Vitest only (by decision, see §7).

---

## 2. Environment and how to run it

| Thing | State |
|---|---|
| Python | **3.13.16** via `py install 3.13`. The machine default is 3.15, where `zstandard` (pulled in by `langgraph`) has no wheel. `.venv` is built on 3.13. |
| venv | `.venv/` with the full `requirements.txt` (`streamlit`, `google-generativeai`, `python-dotenv`, `requests`, `langgraph`, `anthropic` 1.14). |
| Node | **24.20.0 LTS**, npm 11.19 at `C:\Program Files\nodejs`. Needed for tsc, Vitest and npm install inside generated projects. |
| Run | `run.bat`, or **F5** in VS Code (`.vscode/launch.json`, "HumanInTheLoop (Streamlit)": runs from `.venv`, adds Node to PATH, `runOnSave`). `.vscode/` is gitignored, so it stays local. |
| `.env` | `ANTHROPIC_API_KEY` (works), `GITHUB_PAT` (fine-grained, scoped to `pete29/hitl-sandbox`: Contents, Pull requests, Issues read/write; works), `GEMINI_API_KEY` (empty). Gitignored. Never print or commit it. |
| Git identity | Not set globally. Set locally per repo: `Piotr Tomaszewski <piotr.tomaszewski29@gmail.com>`. |

**Running the tests.** Each test is a plain script, not pytest:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python tests/<name>_test.py
```

There are 29 test files. **25 run offline** and all pass. Four call a real model and are skipped
in routine runs: `architect_test`, `workflow_test`, `langgraph_test`, `ollama_test` (needs a
local Ollama). Node must be on PATH for `compile_test`, `install_test` and
`test_execution_test`.

**Rendering the UI headlessly** for a smoke test: `streamlit.testing.v1.AppTest`. To avoid
polluting the real DB, set `Settings.DATABASE_NAME` to a temp file **before** importing any
`database.*` module (their constructors bind the name at import time).

---

## 3. What was done in this session

### Committed (on `master`, local, **4 commits ahead of `origin/master`, not pushed**)

| Commit | What |
|---|---|
| `0538f7e` feat: talk to Claude, with a model chosen per agent | `services/claude_service.py`: streaming, `output_config.effort`, server-side refusal fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`), raises on refusal, truncation or empty answer. `LLMFactory.create(role)`. Per-role models: planner + architect = `claude-opus-5-5`, developer + QA = `claude-sonnet-5-5`. Default provider switched to Claude. |
| `a2f444f` feat: run the free checks before the expensive review, and say what a run cost | Orchestrator reordered: write → structural validator + tsc → only then Architect. QA rewrites only the suites of changed or failing files after a test fix. Code that doesn't compile, fails tests, or never reached the Architect is never recommended. `services/usage_ledger.py` records role, tokens and $ per call; step `step.usage` per task; planning cost shown under the plan. Files a run created and then dropped are removed. |
| `16c358c` feat: make the environment step 0 of every plan | `services/environment_step.py` plus a UI panel: write scaffolding from templates → npm install (human button) → commit scaffolding on the base branch. Tasks stay disabled until Step 0 is done (explicit override checkbox). A task outside a plan commits the scaffolding it wrote. |
| `6964103` feat: give a plan one branch, and undo a rejected task's files | `services/plan_branch.py`: one branch per plan (`feature/plan-<id8>-<slug>`), checked out **before** generation. Tasks commit in run order (`GitAgent.unresolved_before`). `services/task_rollback.py`: reject deletes created files and restores tracked ones (`git checkout -- <paths>`). `Task.branch` and `Task.created_files` added, with a DB migration. |

### Uncommitted (in the working tree; **commit before moving repos**)

1. **`git fetch` allowed in one shape:** `fetch --quiet <remote>`, no refspec, so it only
   touches `origin/*`. Also `merge-base --is-ancestor` (read-only). `GitService.start_point()`
   picks the freshest base that loses nothing: local `main` if it contains `origin/main`,
   otherwise `origin/main` (behind or diverged), local `main` with a note if there's no remote
   or no connection. The note becomes the task's first step, `step.branch`.
2. **A plan has one PR describing the whole plan** (`plan_description` in
   `agents/pull_request_agent.py`): requirement, task checklist with state, score, compile and
   tests per task, files, findings and cost of committed tasks. **Every push of the plan's
   branch rewrites it** (`PullRequestAgent.sync`). GitHub allow-list gained
   `PATCH /pulls/{n}` restricted to `title` and `body`; `state` and `base` are refused.
3. **Delivery feedback:** the plan view shows the plan's PR and a "🔄 Check the PR" button.
   A merged PR moves the requirement to the new lifecycle state `DELIVERED`.
4. **Code context for agents (from the first real E2E run):** `RepositorySurvey.referenced()`
   / `render_referenced()`. Existing files whose exported symbols are named in the task (or
   review) text are given **in full** to the Developer and the Architect (whole-word match,
   12k-char budget, tests excluded). Before this, the Developer knew only the *name*
   `PasswordRule`, guessed ten method names and called whichever existed.
5. **Tests are QA's:** `is_test_path()`. Test files are dropped from the Developer's plan and
   output, and QA no longer writes a suite for a suite (`x.test.test.ts`).
6. **Separate budgets:** `MAX_GATE_FIXES = 2` fixes per round for the free checks,
   `MAX_REVIEW_LOOPS = 3` Architect reviews. Previously compile errors used up the Architect's
   rounds and its blockers were never fixed. A review now always describes the final code,
   unless the free checks failed after it.
7. **Rejecting a plan task reopens it:** its plan execution becomes `FAILED` ("rejected in
   review"), so the plan offers "run again" and dependents wait.
8. **Each plan task shows its review state** (waiting / committed / rejected) and a
   "🔍 Open the task" button. Before, reaching a task's Accept/Reject was only possible from
   the sidebar history.
9. **Bug fixes:** `summary()` dropped non-ASCII letters ("Walidator haseł" became "walidator
   hase") in commit and PR titles; `TaskExecution.duration` crashed the page on mixed
   naive/aware timestamps.
10. New tests: `fetch_test`, `plan_pull_request_test`, `context_files_test`. `governance_test`
    updated to the new fetch and PR-edit rules (still strict). Docs updated: `SECURITY.md`,
    `README.md`, `ARCHITECTURE.md`.

---

## 4. The end-to-end test in progress

- **Sandbox repo:** `https://github.com/pete29/hitl-sandbox.git` (private), cloned at
  `C:\Projects\hitl-sandbox`, `main` at `2fb89bb`. Local git identity is set there.
- **Requirement used:** "Walidator haseł": a `PasswordRule` interface with
  `check(password): string | null`, four rule classes, and `PasswordValidator` taking rules in
  its constructor, with the open/closed principle as a stated constraint.
- **First run** (before fixes 4–7 above): 6 tasks, about **$0.59** total.
  - Tasks 1–2: 95 and 80, APPROVE.
  - Tasks 3–5: 86–91, APPROVE, but they contain junk `*.test.test.ts`.
  - Task 6 (`PasswordValidator`): 45/100 with 5 legitimate blockers (the guessed-method-names
    hack).
  - All 6 were still `WAITING_FOR_APPROVAL` when this was written.
- **Planned next steps for the user:** restart the app, accept 1 then 2, reject 6, 5, 4, 3 (in
  that order), rerun 3–6, then push → open PR → push again (description should update) →
  merge on GitHub → "Check the PR" → `DELIVERED`.
- **Not yet verified live:** push, PR creation, PR description update, merge feedback. Write
  access of the PAT is untested until the first PR is opened.

---

## 5. Architecture quick reference

| Area | Where | Notes |
|---|---|---|
| Orchestration | `workflows/workflow_orchestrator.py` | `Gates`, `RunFiles`, loop with two budgets, test loop, recommendation override. |
| LLM | `services/llm_factory.py`, `claude_service.py`, `ollama_service.py`, `gemini_service.py` | Role-based; all record usage. |
| Cost | `services/usage_ledger.py`, `Settings.CLAUDE_PRICES` | ASCII only in output (see §8). |
| Repo facts | `services/repository_survey.py`, `repository_context.py`, `environment_step.py` | Derived, never stored. |
| Validation | `services/structure_validator.py`, `type_checker.py`, `test_runner.py` | Deterministic. |
| Git | `services/git_service.py` (allow-list), `agents/git_agent.py`, `services/plan_branch.py`, `task_rollback.py` | Stage by name, never `git add .`. |
| GitHub | `services/github_service.py` (allow-list + PATCH field limits), `agents/pull_request_agent.py`, `issue_agent.py` | No merge, close or delete is reachable. |
| Persistence | `database/*.py`, SQLite | `task_repository` columns are **positional**: append new ones at the end of `COLUMNS` and add them to `ADDED_COLUMNS`. `save()` is a plain INSERT, so a task cannot be saved twice. |
| UI | `app.py` (about 3,000 lines), `services/translations.py` | Every visible string goes through `t()`, in Polish and English. `translation_test` enforces it. |

**Git safety model (current):**
- **Allowed:** `add`, `branch`, `checkout`, `commit`, `diff`, `fetch` (one shape), `ls-files`,
  `merge-base --is-ancestor`, `push` (no force, delete, mirror or tags; never to
  `main`/`master`/`develop`/`release`/`trunk`), `remote get-url`, `rev-parse`, `status`,
  `symbolic-ref`.
- **Refused:** `pull`, `clone`, `merge`, `rebase`, `reset`, `tag`, `cherry-pick`, `submodule`.

**Human gates:** commit, push, PR creation, npm install, scaffolding commit, merge (on GitHub)
are all explicit human actions. Nothing installs, commits or pushes on its own.

---

## 6. Known gaps and the backlog (in priority order)

1. **Finish the live E2E** (§4) and fix what it finds. The first run found four real bugs; expect
   more in push and PR.
2. **The planner is still blind to code.** It gets only counts, folders and tooling state, not
   files or exports. Plan: give it `survey().render()` plus referenced files; make tasks declare
   `creates` / `modifies`; add a deterministic `PlanValidator` (modifies ⊆ existing ∪ created by
   dependencies; creates ∉ existing; file dependencies imply task dependencies). Report
   problems, never repair them silently.
3. **PR review comments don't flow back** to the Developer (roadmap: "Review feedback").
4. **Prompt caching:** prompts are single strings with the variable part first. Restructure as a
   stable prefix (rules, repo listing, referenced files) plus `cache_control`.
5. **Run-all blocks the UI** (synchronous in the Streamlit request; no worker or queue).
6. **Single tasks outside a plan** are generated on whatever branch is checked out (only planned
   tasks enter a branch first).
7. **The structural filter on Architect claims is text-based**; new phrasings can slip through
   as noise.
8. **`google.generativeai` is deprecated** (switch to `google.genai` if Gemini is ever used).

---

## 7. Decisions and the user's preferences (binding)

- **Reply to the user in Polish.** Code, comments, commit messages and docs stay in English.
- **TypeScript-only** factory for now. Don't propose multi-stack.
- **Azure (Boards and Repos) is on hold.** GitHub only. Don't build Azure pieces unprompted.
- **Branch strategy for target repos: one branch and one PR per plan, one commit per task**
  (stacked branches rejected: they'd need merge and rebase).
- **`git fetch` is allowed** (decided 2026-10-14), in the restricted shape above.
- **Goal set by the user:** a tool that meets requirements *without errors* and *without wasting
  tokens*. Cheap deterministic checks before expensive model calls; measure cost before
  optimising.
- **This repo (HumanInTheLoop itself): commit straight to `master`**, no feature branches.
  **Push only when asked.** The repos the *factory* manages are the opposite: branches and PRs
  are the product.
- **Commit messages:** `feat:` / `fix:` plus a lowercase, behaviour-describing subject, and a body
  explaining why. Code style: vertical spacing, comments that explain *why*, matching the
  surrounding file.
- The user prefers least-privilege credentials (chose a fine-grained PAT over reusing the Git
  Credential Manager token).

---

## 8. Traps already found (don't rediscover them)

- **Line endings:** every file in this repo is **CRLF**, in the working tree *and* in HEAD
  (`core.autocrlf=true`). Scripts that edit files must read with `newline=""`, work on `\n`,
  and write back with `newline="\r\n"`. Searching for `"\n"`-joined text in a raw read fails.
- **Windows console is cp1250:** `print()` of `→`, `Σ`, `⬜` raises `UnicodeEncodeError` and
  kills the run. Keep console output ASCII (the usage ledger does). Use
  `PYTHONIOENCODING=utf-8` for test scripts. `launch.json` sets `PYTHONUTF8=1`.
- **Heredocs:** bash heredocs with Python containing `'`, `\n` or regex escapes broke several
  times. Write a script file and run it instead.
- **PowerShell's PATH can be stale** after installing Node. The bash tool and new terminals see
  it; old processes don't.
- **Streamlit `AppTest`** needs an absolute script path when the test script lives elsewhere.
- **Git Credential Manager** may open a browser login on first contact with a private repo; a
  command looks hung until the user logs in.
- **Task and plan DB rows** carry `created_at` with a timezone. Hand-made test data must too.
- **The `.env` token** was once pasted twice on one line (186 chars). If GitHub returns 401,
  check the length (fine-grained PAT is 93) before anything else.

---

## 9. Memory files

The previous agent kept notes in
`C:\Users\piotr\.claude\projects\c--Projects-HumanInTheLoop\memory\`
(`factory-vision.md`, `commit-to-master.md`). §7 contains everything in them. If the repo
moves, that path changes with the project folder name.
