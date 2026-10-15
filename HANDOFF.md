# DevLoop: handoff

Read this before you touch the code. It covers what the project is, what changed in the
session of 14–15 October 2026, what is decided, what is still open, and the traps already found.
`README.md` and everything under `docs/` are current and go deeper. This file is the map.

---

## 1. What this is

**DevLoop** is an **AI software factory with
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

**Stack of the tool:** Python 3.13, Streamlit UI (`app.py` + `ui/`), SQLite (`human_in_the_loop.db`),
Anthropic SDK. **Stack it generates:** TypeScript + Vitest only (by decision, see §7).

---

## 2. Environment and how to run it

| Thing | State |
|---|---|
| Python | **3.13.16** via `py install 3.13`; the machine default is 3.15. `.venv` is built on 3.13, the version CI runs. |
| venv | `.venv/` with `requirements.txt` (`streamlit`, `python-dotenv`, `requests`, `anthropic` 1.14); `pyflakes` installed locally as a check, not a requirement. |
| Node | **24.20.0 LTS**, npm 11.19 at `C:\Program Files\nodejs`. Needed for tsc, Vitest and npm install inside generated projects. |
| Run | `run.bat`, or **F5** in VS Code (`.vscode/launch.json`, "DevLoop (Streamlit)": runs from `.venv`, adds Node to PATH, `runOnSave`). `.vscode/` is gitignored, so it stays local. |
| `.env` | `ANTHROPIC_API_KEY` (works), `GITHUB_PAT` (fine-grained, scoped to `pete29/hitl-sandbox` and `pete29/DevLoop`: Contents, Pull requests, Issues read/write; works), `GITHUB_ADMIN_PAT` (creating repositories). Gitignored. Never print or commit it. |
| Git identity | Not set globally. Set locally per repo: `Piotr Tomaszewski <piotr.tomaszewski29@gmail.com>`. |

**Running the tests.** Each test is a plain script, not pytest. All offline ones:

```bash
.venv/Scripts/python tests/run_offline.py
```

One of them:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python tests/<name>_test.py
```

CI (`.github/workflows/tests.yml`, Windows) runs the offline suites on every PR and on `main`.

**The eval** (`evals/run_eval.py <label>`, ~$0.25, never in CI) runs six real cases on copies of
`evals/fixture` - four tasks, a task needing an npm package, a planned requirement - and writes a
report; `evals/compare.py` compares two. Baseline `2026-10-15-baseline-v2`: 6/6, $0.2454. Run it
around any prompt, model or effort change.

There are 44 test files. **41 run offline** and all pass. Three call a real model and are skipped
in routine runs: `architect_test`, `workflow_test`, `ollama_test` (needs a
local Ollama). Node must be on PATH for `compile_test`, `install_test` and
`test_execution_test`.

**Rendering the UI headlessly** for a smoke test: `streamlit.testing.v1.AppTest`. To avoid
polluting the real DB, set `Settings.DATABASE_NAME` to a temp file **before** importing any
`database.*` module (their constructors bind the name at import time).

---

## 3. History

### Before 15 October 2026 (old repository, `C:\Projects\HumanInTheLoop`, branch `master`)

Claude per agent with streaming, effort and server-side refusal fallback; free checks before
the paid review and a usage ledger; Step 0 (scaffolding, npm install, scaffolding commit); one
branch per plan with tasks committed in run order and rejected files undone; restricted
`git fetch` and a start point that loses nothing; one PR per plan rebuilt on every push;
`DELIVERED` on merge; referenced files given in full to Developer and Architect; tests are
QA's (`is_test_path`); separate budgets (`MAX_GATE_FIXES`, `MAX_REVIEW_LOOPS`).

The project then moved to **`C:\Projects\DevLoop`**, remote `https://github.com/pete29/DevLoop.git`,
branch **`main`**. The old history did not come along: it all landed as one commit, `587c0c2`.

### 15 October 2026 (this repository, all on `main`, **not pushed**)

| Commit | What |
|---|---|
| `587c0c2` | the factory imported from the old repository |
| `70ed432` `11af323` | docs brought up to date; the app renamed **DevLoop** (title, commit/PR footers, issue labels `devloop:*`). The DB file keeps its name `human_in_the_loop.db` so existing tasks are not orphaned. |
| `9f31cc5` | **fix:** a committed task can no longer be rejected (`roll_back` refuses; the button is disabled). Found live: task 3 was accepted, then rejected, and its commit with a junk `*.test.test.ts` stayed on the branch. |
| `802a162` | **fix:** a finding ending in a colon keeps the bullets after it (one warning reached the PR as four); the Architect must answer in English (a Polish requirement got a Polish review the filter cannot read). |
| `693d987` | **fix:** commit subjects use the task's title line only; PR findings and costs carry the checklist label ("3. …"). |
| `7865452` | the task opens in a **large dialog** (`st.dialog`) instead of below the plan; run-all no longer opens it; the "Check the PR" button is no longer cut off. |
| `4d9859b` | plans made from an issue use **`feature/issue-<n>-<slug>`**; every plan for that issue shares the branch and PR (decision, §7). Plan lookup by branch prefers the plan whose run produced the task; the PR lists an earlier plan's commits. |
| `10c26fa` | **Send back for revision:** a third answer beside accept/reject. Chosen Architect findings and/or human notes go to the Developer as blockers; `WorkflowOrchestrator.revise()` edits the files on disk and reruns checks, review (history carried on), QA and tests. Notes are appended to the task description. The old record becomes `TaskStatus.REVISED`; the plan points at the new one. |
| `f9af41a` | **Issues both ways:** "Create a GitHub issue" from a requirement; "Split into issues" (`agents/story_splitter.py`, planner model, 2–6 stories, human edits and confirms). Allow list: `POST /issues` with `title`/`body` only. Plans with more than `SPLIT_HINT_TASKS` (6) tasks suggest the split. |
| `5d1855e` | split children linked as real GitHub **sub-issues** (`POST /issues/{n}/sub_issues`, `sub_issue_id` only); the sidebar shows issues as a tree with parent progress; the plan shows its branch (local / on GitHub / link), DevLoop commits on it, and when it continues an earlier plan. |
| PR for #1 | **fix:** a `REVISED` record held up the commit of its own revision (`GitAgent.unresolved_before`), and an approved task whose commit failed could not be accepted again. Found live on hitl-sandbox issue #2. From here on, every step is an issue and a PR (§7). |
| `2dfa3ff` | **Repositories from the file system:** "Choose a folder…" (tkinter `askdirectory`, the app runs locally) fills path and name; "New repository" (`services/repository_setup.py`) creates a GitHub repo with `auto_init` first, then `init` → `remote add origin` → `fetch` → checkout `main` tracking `origin/main`. Git allow list: `init` (one shape), `remote add origin` (once, no credentials). GitHub: `POST /user/repos` (name, private, description, auto_init). Token: `GITHUB_ADMIN_PAT` if set, else `GITHUB_PAT`. Not tried live: the current PAT is scoped to hitl-sandbox and cannot create repositories. |
| `637da3d` | **The planner sees the code:** file listing with exports plus referenced files in full; tasks declare `creates` / `modifies`; `services/plan_validator.py` reports false assumptions (creates an existing file, modifies a missing one, file dependency without task dependency, two creators, test files, unsafe paths). File lists reach the Developer in the task prompt (`Create: …`, `Modify: …`). |

---

## 4. Live end-to-end state (sandbox)

- **Sandbox repo:** `https://github.com/pete29/hitl-sandbox.git` (private), cloned at
  `C:\Projects\hitl-sandbox`. Local git identity is set there.
- **"Walidator haseł" (first plan): delivered.** PR #1 merged (merge commit), requirement
  `DELIVERED`. Verified live: push, PR creation (PAT has write), merge read-back. Rerun of tasks
  3–6 cost $0.19 (≈$0.05/task) against $0.59 for 6 tasks before the fixes; task 6
  (`PasswordValidator`) used the real `PasswordRule` and scored 92 instead of 45.
- **Issue #2** "Lowercase rule and password strength": imported, planned on
  `feature/issue-2-lowercase-rule-and-password`, not pushed yet. The user was reviewing the
  `LowercaseRule` task (a good case for "Send back for revision": the rule uses `/[a-z]/`).
- **Issue #3** "Password policy toolkit": split live into #4 blocklist, #5 policies,
  #6 explanations, #7 generator. #4–#7 are linked as sub-issues of #3 (linked by hand with the
  new service method after the feature landed; verified on GitHub).
- **Still not verified live:** the PR description rewriting itself on a *later* push (PR #1 was
  opened after the last push), "Send back for revision" against a real model, the planner's
  `creates`/`modifies` with a real model, and the split's sub-issue linking from the button
  (the method itself worked live).
- **Next live test:** plan #4 (smallest) → run task 1 → accept → push → open PR → run task 2 →
  accept → push → the PR description must update → merge → 🔄 → `DELIVERED`.

---

## 5. Architecture quick reference

| Area | Where | Notes |
|---|---|---|
| Orchestration | `workflows/workflow_orchestrator.py` | `execute()` and `revise()` share `finish()`: two budgets, test loop, recommendation override. |
| Background runs | `services/plan_runner.py`, `database/run_repository.py`, `models/plan_run.py` | Worker process per run (`python -m services.plan_runner <id>`); the page reads `plan_runs` and a 3 s fragment. Worker writes only its own columns. `DEVLOOP_DATABASE` overrides the DB file. |
| Planning | `agents/planner_agent.py`, `services/plan_validator.py`, `agents/story_splitter.py` | Planner sees `survey().render()` + referenced files; validator reports, never repairs. |
| LLM | `services/llm_factory.py`, `claude_service.py`, `ollama_service.py`, `prompt_cache.py` | Role-based; all record usage. Agents call `ask(llm, cached, prompt)`: cached blocks must be byte-identical across the calls that should share them (`tests/prompt_cache_test.py`). |
| Cost | `services/usage_ledger.py`, `Settings.CLAUDE_PRICES` | ASCII only in output (see §8). |
| Repo facts | `services/repository_survey.py`, `repository_context.py`, `environment_step.py` | Derived, never stored. |
| Validation | `services/structure_validator.py`, `type_checker.py`, `test_runner.py` | Deterministic. |
| Git | `services/git_service.py` (allow-list), `agents/git_agent.py`, `services/plan_branch.py`, `task_rollback.py` | Stage by name, never `git add .`. `plan_branch.of(plan)` is the one way to get a plan's branch. |
| GitHub | `services/github_service.py` (allow-list + per-call field limits), `github_issue_service.py`, `agents/pull_request_agent.py`, `issue_agent.py` | No merge, close or delete is reachable. |
| Persistence | `database/*.py`, SQLite | `task_repository` columns are **positional**: append new ones at the end of `COLUMNS` and add them to `ADDED_COLUMNS`. `save()` is a plain INSERT, so a task cannot be saved twice. Plan tasks are JSON; new fields need a default in `_parse_tasks`. |
| UI | `app.py` (the page, ~50 lines), `ui/*.py` (its parts; views are short functions calling named sections, modules ordered top-down), `services/translations.py` | Every visible string goes through `t()`, in Polish and English. `translation_test` enforces it. The task view is `task_view()` shown via `st.dialog(width="large")`. |

**Git safety model (current):**
- **Allowed:** `add`, `branch`, `checkout`, `commit`, `diff`, `fetch` (one shape), `init`
  (one shape, new folders only), `ls-files`, `merge-base --is-ancestor`, `push` (no force,
  delete, mirror or tags; never to `main`/`master`/`develop`/`release`/`trunk`),
  `remote get-url`, `remote add origin <url>` (only without an origin), `rev-parse`, `status`,
  `symbolic-ref`.
- **Refused:** `pull`, `clone`, `merge`, `rebase`, `reset`, `tag`, `cherry-pick`, `submodule`.

**GitHub reads added for review feedback and CI:** a PR's inline comments, reviews and
conversation; a commit's Actions runs and jobs; a failed job's log. These need `Actions: Read-only`
on `GITHUB_PAT` (a fine-grained token cannot hold `Checks`, hence the Actions API).

**GitHub writes (all on a human's click):** create PR; PATCH PR `title`/`body`; create issue
(`title`/`body`); link sub-issue (`sub_issue_id`); comment on an issue; PATCH issue
`labels`/`state`; create a repository (`name`/`private`/`description`/`auto_init`, with
`GITHUB_ADMIN_PAT` when set).

**Human gates:** commit, push, PR creation, npm install, scaffolding commit, filing issues,
merge (on GitHub) are all explicit human actions. Nothing installs, commits, files or pushes on
its own.

---

## 6. Known gaps and the backlog (in priority order)

1. **Finish the live checks** in §4 (PR description update on a later push; revision, planner
   file claims and split linking against the real model) and fix what they find.
2. **Review comments on GitHub** are read and sent back on a click (`services/review_feedback.py`);
   DevLoop does not reply to or resolve them on GitHub.
3. **Output tokens are the bill.** Prompt caching is in (6.7% saved on two real tasks); the
   Architect's review is now three findings of two sentences (-32% per review, effort kept
   high). Plans show their total and stop at `PLAN_COST_LIMIT` (`services/costs.py`).
7. **The structural filter on Architect claims is text-based**; new phrasings can slip through
   as noise. The review itself is structured JSON on Claude (`REVIEW_SCHEMA`); the text
   format and its parser remain only for providers without structured outputs.

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
- **This repo (DevLoop itself): commit straight to `main` when a stage of work is finished,
  and push.** No feature branches, no pull requests (tried for two steps on 2026-10-15, then
  dropped by the user). The plan lives as issues in `pete29/DevLoop`; a stage's commit says
  `Closes #<n>`, which closes its issue on push. Docs (`.md`) go in the same commit as the code.
  CI runs the offline suites on every push to `main`.
- **Commit messages:** `feat:` / `fix:` plus a lowercase, behaviour-describing subject, and a body
  explaining why. Code style: vertical spacing, comments that explain *why*, matching the
  surrounding file.
- The user prefers least-privilege credentials (chose a fine-grained PAT over reusing the Git
  Credential Manager token).
- **The app is called DevLoop** (decided 2026-10-15). The old working name is gone.
- **One branch per issue** (decided 2026-10-15): a plan made from an issue uses
  `feature/issue-<n>-<slug>`, and a second plan for the same issue continues on it and in its PR.
- **Large requirements are split into issues** (like Azure user stories), linked as GitHub
  sub-issues; small ones stay one branch with a commit per task. The split is proposed by the
  model and confirmed by a human; nothing is filed automatically.
- **Merge PRs with "Create a merge commit"**, so one commit per task survives on `main`.
- **"New repository" creates on GitHub too** (decided 2026-10-15), private by default, with a
  separate `GITHUB_ADMIN_PAT` for the account-level permission it needs.
- **Keep the `.md` files current** with every change, README included.

---

## 8. Traps already found (don't rediscover them)

- **Line endings:** every file in this repo is **CRLF**, in the working tree *and* in HEAD
  (`core.autocrlf=true`). Scripts that edit files must read with `newline=""`, work on `\n`,
  and write back with `newline="\r\n"`. Searching for `"\n"`-joined text in a raw read fails.
- **Windows console is cp1250:** `print()` of `→`, `Σ`, `⬜` raises `UnicodeEncodeError` and
  kills the run. Keep console output ASCII (the usage ledger does). Use
  `PYTHONIOENCODING=utf-8` for test scripts. `launch.json` sets `PYTHONUTF8=1`.
- **Heredocs:** bash heredocs with Python containing `'`, `\n` or regex escapes broke several
  times (in this session `\\n` arrived as a real newline). Write the script with the Write tool
  and run it instead.
- **`runOnSave`:** saving `app.py` while the app runs reruns the page. Every task runs in a
  detached worker now (a task on its own is a plan of one task), so none is affected.
- **Windows `os.kill(pid, 0)` terminates the process** instead of testing it. Use
  `plan_runner.process_alive`.
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

Agent memory now lives in `C:\Users\piotr\.claude\projects\c--Projects-DevLoop\memory\`
(`working-preferences.md`). The notes kept before the move are in
`C:\Users\piotr\.claude\projects\c--Projects-HumanInTheLoop\memory\`
(`factory-vision.md`, `commit-to-master.md`); §7 contains everything in them. If the repo
moves again, the path changes with the project folder name.
