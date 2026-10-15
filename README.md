# 👑 DevLoop

[![tests](https://github.com/pete29/DevLoop/actions/workflows/tests.yml/badge.svg)](https://github.com/pete29/DevLoop/actions/workflows/tests.yml)

An AI software factory with a human gate in the middle.

A requirement goes in. AI agents plan it, write it, review it and test it.
A human approves every change. Git and GitHub carry the approved work to a
pull request, and a human merges it.

```text
Requirement (typed by hand, or imported from a GitHub issue)
  → too large? split into issues (sub-issues, one PR each)
  → Planner (Opus)              sees the code; tasks + files they touch,
                                checked in code against the repository
  → Step 0: environment         scaffolding, npm install, scaffolding commit
  → per task, on the plan's branch:
      Developer (Sonnet)        one call per file
      Free checks               structural validator + tsc (no model)
      Architect (Opus)          reviews only code that passed the free checks
      QA (Sonnet)               one Vitest suite per source file
      Compile + tests           real tsc, real Vitest
  → Human: accept / send back / reject
                                accept    = commit on the plan's branch
                                send back = your notes, the Developer revises
                                reject    = the task's files are undone
  → Push → pull request         one PR per plan, description rebuilt on every push
  → Human merges on GitHub → "Check the PR" → requirement DELIVERED
```

**The core rule: facts belong to code, reasoning belongs to AI.** Anything
that can be decided mechanically — does a file exist, does an import
resolve, does it compile, is a branch behind `origin`, which file exports a
symbol — is decided in code and never asked of a model. Every stage of the
pipeline is either deterministic or AI, never both. Cheap checks run before
expensive model calls, and every run reports what it cost.

The tool is written in Python (Streamlit, SQLite, the Anthropic SDK). The
code it generates is **TypeScript with Vitest**, and only that.

---

## Requirements

| What | Notes |
|---|---|
| Python 3.13 | the version the suites and CI run on |
| Node.js 24 LTS | `tsc`, Vitest and `npm install` run inside the generated projects |
| git | branches, commits and pushes in the target repository |
| An Anthropic API key | the default provider |
| A GitHub fine-grained token | optional; issues, push feedback and pull requests |
| A second token with `Administration: write` | optional; only for creating GitHub repositories (`GITHUB_ADMIN_PAT`) |

A local Ollama remains as an alternative provider; see
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

---

## Setup

```powershell
git clone https://github.com/pete29/DevLoop.git
cd DevLoop

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Create a `.env` in the project root (it is gitignored):

```env
ANTHROPIC_API_KEY=your_key

# Only for issues, pull requests and delivery feedback
GITHUB_PAT=your_token

# Only for "New repository" on GitHub (Administration: write)
GITHUB_ADMIN_PAT=
```

Use a **fine-grained** GitHub token scoped to the target repositories only,
with `Contents`, `Pull requests` and `Issues` set to read and write, and
`Checks` and `Actions` set to read (for the PR's CI). Without
it the GitHub buttons are disabled and say so; nothing else breaks.

---

## Running

```powershell
.\run.bat
```

or, with the virtual environment active, `streamlit run app.py`. In VS Code,
**F5** works too if you add a `debugpy` launch configuration that runs the
`streamlit` module from `.venv` with Node on `PATH`. The app opens at
`http://localhost:8501`.

---

## Using it

### 1. Register a repository

Sidebar → **📦 Repositories** → **➕ Add repository** → **📁 Choose a
folder…** opens the system's folder window and fills the path and the name
(the folder's). Typing a path works too, and fills the name. The added
repository becomes the selected one. Point it at a sandbox: generated files
overwrite files whose paths collide, which shows up afterwards in the diff
as `modified`.

**🆕 New repository** creates one: a folder with git on `main` and, by
default, a private GitHub repository set as its `origin`, ready for plans,
pull requests and issues. GitHub goes first and creates the repository with
a first commit, so `main` exists and a pull request has a base; the local
side is then `init`, `remote add origin`, `fetch` and a checkout of `main`
(a clone made of allowed steps — `clone` itself is refused). If GitHub
refuses, nothing is left behind locally. Creating a repository needs a
token with `Administration: write`: `GITHUB_ADMIN_PAT` is used when set, so
the everyday `GITHUB_PAT` keeps its narrow scope.

### 2. Write a requirement, or import one

**🧠 Requirements** holds a title and a description: user stories,
constraints, acceptance criteria. **📥 GitHub Issues** turns an open issue of
the repository's remote into a requirement; importing it again updates it.

The other way works too. **📤 Create a GitHub issue** files a requirement
written here as an issue, so its plan gets the issue's branch and its pull
request closes the loop on GitHub. **✂️ Split into issues** is for a
requirement too large for one pull request: the Planner proposes user
stories, you edit and pick them, and each becomes its own issue, and later
its own plan, branch and pull request. The children are linked under the
parent as GitHub **sub-issues**, so the parent shows their progress. A
small requirement needs none of this: one branch, one pull request, a
commit per task. A plan with more than `SPLIT_HINT_TASKS` tasks suggests
the split.

The sidebar lists issues as a tree: sub-issues under their parent, the
parent with its progress (`#3 Password policy toolkit · 1/4`).

### 3. Plan it

The Planner turns a requirement into tasks with priorities and
dependencies. It **sees the code**: the repository's files with what each
exports, and in full the files whose symbols the requirement names. Every
task says which source files it **creates** and which it **modifies**, and
the plan shows them.

What can be checked is checked in code (`PlanValidator`), and reported above
the plan — never repaired silently:

- dependency problems: a task depending on itself or on a missing task, cycles;
- a task creating a file that already exists — that part is probably done;
- a task modifying a file that neither exists nor comes from a task it
  depends on, or another task's file without depending on that task;
- two tasks creating one file, planned test files, paths outside the repo.

A task whose dependencies have not finished is blocked.

**➕ Finish / extend the plan** (on the requirement, per plan) continues a
plan instead of planning again: the plan's branch is entered first, the
planner is given the requirement, the code on that branch and the list of
tasks already done, and plans only what is missing, numbering on from the
done tasks and free to depend on them. Done tasks stay; unfinished and
failed ones are replaced; `PlanValidator` checks the new tasks; the branch
and the pull request stay the same.

Every plan gets **one branch** (`feature/plan-<id8>-<slug>`), checked out
before anything is generated. A plan made from a GitHub issue is named after
the issue instead (`feature/issue-<number>-<slug>`), and a second plan for
the same issue continues on that branch and in its pull request. Its base is
the freshest point that loses nothing: local `main` if it already contains
`origin/main`, otherwise `origin/main`. The plan shows its branch, whether it
exists locally and on GitHub, the DevLoop commits already on it, and when it
continues an earlier plan's branch.

### 4. Step 0: the environment

Before the first task, the plan's environment panel:

1. writes the missing `package.json`, `tsconfig` and Vitest config from
   templates (an existing file is never touched),
2. runs `npm install` — **only when you press the button**,
3. commits the scaffolding on the base branch.

Tasks stay disabled until Step 0 is done, unless you explicitly override it.

### 5. Run the tasks

Each task goes through the pipeline above:

- The **Developer** reads the repository first. Existing files whose
  exported symbols are named in the task are given to it in full, so it
  builds on real interfaces instead of guessing method names. It writes one
  file per call; test files are QA's and never the Developer's.
- The **free checks** — structural validator and `tsc` — run before the
  Architect sees anything, with their own budget (`MAX_GATE_FIXES`). A
  missing npm package stops the task there and is offered for installation
  (below).
- The **Architect** reviews design only (coupling, abstractions, SOLID),
  up to `MAX_REVIEW_LOOPS` times, in at most three findings of two sentences,
  answered as JSON in a schema (score, recommendation, findings with severity
  and file) rather than prose to parse
  each. Claims about things a compiler decides are filtered out.
- **QA** writes one Vitest suite per source file; after a fix only the
  suites of changed or failing files are rewritten.
- The generated tests are **actually run**. Code that does not compile,
  fails its tests, or never reached the Architect is never recommended.

Tasks run **in the background**, in a worker process: **Run task** and
**⏩ Run the whole plan** start one, and the plan shows what it is on, how
far it got and the last lines of its console, refreshed every few seconds.
The tab can be closed and the page reloaded; the run carries on.
A task described on its own (**Generate code** at the bottom of the page) becomes a plan of one task: it gets its branch before anything is generated, runs in the background worker, and has a pull request and a cost like any planned task. **⏹ Stop
after this task** stops it between tasks, and a worker that died is marked
`INTERRUPTED` on the next page load.

**Packages a task needs.** The Developer is told which packages the project
has. When the code imports one it lacks (or a Node built-in such as
`crypto` without `@types/node`), the free checks stop the task there - no
fixes are paid for, since no rewrite installs a package - and the task
window offers **📦 Install <names> and check again**: `npm install
<names> --save --ignore-scripts`, registry names only, then the same files
through the compiler, the Architect, QA and the tests.

Each task shows its tokens and cost per agent.

**What it costs.** Every task stores its dollars; the plan shows its total —
planning, every attempt, every revision, and attempts that failed before a
record was saved — and the sidebar shows the month. `PLAN_COST_LIMIT`
(default $5, 0 for none) stops a background run **before** a task once the
plan has spent that much, never inside one; the run buttons are disabled
and the plan says why.

### 6. Accept, send back, or reject

**🔍 Open the task** shows it in a window over the page: code, review,
tests, diff and git. Three answers:

- **✅ Accept** commits the task's files on the plan's branch, in run order.
- **🔁 Send back for revision**: pick Architect findings and/or write your
  own notes. The Developer edits the existing files with them as blockers,
  and the free checks, the Architect, QA and the tests run again. Your notes
  become part of the task. The old version reads `REVISED`.
- **❌ Reject** deletes the files the task created, restores the tracked
  files it changed, and reopens the task in the plan so it can run again;
  tasks that depend on it wait. A committed task cannot be rejected.

### 7. Push, pull request, delivery

**⬆️ Push** sends the plan's branch to `origin`. The first push lets you
open **one pull request for the whole plan**: the requirement, a task
checklist with states, scores, compile and test results, files, findings
and cost. Every later push rewrites that description.

**CI on the pull request.** **🧪 Check the PR's CI** reads the check runs
of the request's latest commit (✅ / ❌ / ⏳). For a failed GitHub Actions
job it shows the end of the job's log, and **Send this failure back for
revision** gives it to the task you choose as revision notes; after you
accept and push, CI runs again. Read only: nothing is re-run or changed.
The token needs `Checks: read` and `Actions: read` for this.

**Review on GitHub comes back.** While the plan's pull request is open,
**💬 Load the PR's review comments** reads what reviewers wrote: comments on
lines of the diff, the text of reviews, and the conversation (bare approvals
and DevLoop's own comments are left out). Tick the ones to act on; each goes
to a task — an inline comment to the task that last wrote its file, a
general one to the task you choose. Every task gets its comments as
revision notes, through the same **Send back for revision** as notes typed
in the app; accept and push, and the pull request's description updates. A
comment sent back is remembered and not offered again. Reading is all
DevLoop does on the pull request: it never comments, reviews or resolves.

You merge on GitHub. **🔄 Check the PR** in the plan view then moves the
requirement to `DELIVERED`. When the work came from an issue, the issue gets
a comment with the pull request; it is never closed automatically.

---

## What the agents may and may not do

Enforced in code, each with a test. Details in
[docs/SECURITY.md](docs/SECURITY.md).

**Human gates.** Commit, push, opening a pull request, `npm install`, the
scaffolding commit and merging are explicit human actions. Nothing
installs, commits or pushes on its own.

**Files** are written only inside the selected repository. Paths with `..`,
absolute paths and drive letters are rejected, not cleaned up.

**git** is limited to an allow list: `add`, `branch`, `checkout`, `commit`,
`diff`, `fetch` (only `fetch --quiet <remote>`, which touches nothing but
`origin/*`), `init` (only `--quiet --initial-branch=<name>`, in a folder
without a repository), `ls-files`, `merge-base --is-ancestor`, `push`,
`remote get-url`, `remote add origin <url>` (only where there is no origin,
no credentials in the URL), `rev-parse`, `status`, `symbolic-ref`. `push` may not
force, delete, mirror or push tags, and never targets `main`, `master`,
`develop`, `release` or `trunk`. `pull`, `clone`, `merge`, `rebase`,
`reset`, `tag`, `cherry-pick` and `submodule` are refused. Staging is by
file name, never `git add .`.

**GitHub** is limited to a fixed set of calls matched on method and path.
A new issue may carry only `title` and `body`; linking a sub-issue only the
child's id; a new repository only its name, visibility, description and a
first commit (never a template, team or organisation). A `PATCH` on a pull request may carry only `title` and `body`; on
an issue only `labels` and `state`. Merging, closing and deleting are not
reachable.

**Credentials** come from the environment, are never stored in the
database, and are stripped from error text.

---

## Configuration

Everything lives in [config/settings.py](config/settings.py). The models
are chosen per agent — Opus where judgement is scarce, Sonnet where volume
is:

```python
LLM_PROVIDER = LLMProvider.CLAUDE

CLAUDE_MODELS = {
    "planner": "claude-opus-5-5",
    "architect": "claude-opus-5-5",
    "developer": "claude-sonnet-5-5",
    "qa": "claude-sonnet-5-5",
}

MAX_GATE_FIXES = 2      # fixes the free checks may ask for per round
MAX_REVIEW_LOOPS = 3    # Architect reviews per task
MAX_TEST_LOOPS = 1      # how often failing tests may send work back
```

**Prompt caching.** Agents send what repeats as separate blocks, first, and
Claude caches each (`services/prompt_cache.py`, `ClaudeService.generate_cached`):

- the **Architect's rules** — identical in every review, so every task of a
  plan after the first reads them from the cache;
- the **Developer's task context** (role, task, repository listing, files
  the task names) — identical in the planning call and every file call of
  the task — and the **file list**, identical for every file of a round.

A cache write costs 1.25× input and a read 0.05× (Opus 5.5) or 0.1×
(Sonnet 5.5), so only text sent again within five minutes is cached; the
planner (one call) and QA (rules under the 512-token minimum) are not.
Measured on two real tasks: $0.100 against $0.108 for the same tokens
uncached, 6.7% — the bill is mostly output tokens. The saving grows with the
repository (listing and referenced files sit in the cached prefix) and with
the number of tasks in a plan. The cost line of every task counts cache
reads and writes at their own prices.

`CLAUDE_PRICES` drives the cost report. `AUTO_BOOTSTRAP` and
`ENABLE_PACKAGE_INSTALLATION` control Step 0; the second removes the
`npm install` button entirely. `SPLIT_HINT_TASKS` (6) is the plan size above
which a split into issues is suggested. `PLAN_COST_LIMIT` (5.0 dollars) is
what one plan may spend before no new task starts.

---

## Tests

Each test is a plain script, not pytest. All the offline ones at once, from
the project root:

```bash
.venv/Scripts/python tests/run_offline.py
```

or one of them:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python tests/<name>_test.py
```

CI runs the offline suites on every pull request and on `main`
([`.github/workflows/tests.yml`](.github/workflows/tests.yml)): Windows,
Python 3.13, Node 24, no secrets.

**The eval** measures the factory itself: four tasks from
`evals/cases.json`, each through the real pipeline on a fresh copy of
`evals/fixture` (a small TypeScript project with code to build on). Per
case: compiles, tests pass, the Architect's score and verdict, review
rounds, files, cost and time.

```bash
.venv/Scripts/python evals/run_eval.py my-label
.venv/Scripts/python evals/compare.py evals/reports/2026-10-15-baseline.json evals/reports/<new>.json
```

It calls the real model (about $0.12 for the four cases) and never runs in
CI. Run it before and after changing a prompt, a model or an effort. The
baseline: 4/4 passed, scores 93-96, one review round each, $0.1163.

There are 38 test files. 35 run offline, against fake transports and
throwaway repositories; `compile_test`, `install_test` and
`test_execution_test` need Node on `PATH`. Three call a real model and are
skipped in routine runs: `architect_test`, `workflow_test`,
and `ollama_test` (which needs a local Ollama).

---

## Project structure

```text
agents/        planner, story splitter, developer, architect, QA, test execution,
               git, pull request, issue
workflows/     the orchestrator and the recommendation policy
services/      LLM providers, usage ledger, repository survey, plan validator,
               validation, tsc, Vitest, git, GitHub, plan branches, rollback,
               translations
models/        the data the pipeline passes around
database/      SQLite persistence: repositories, requirements, plans, tasks
tests/         see above
evals/         the eval: cases, the fixture project, reports
docs/          architecture, workflow, security, configuration, testing, roadmap
app.py         the Streamlit page: session state, then the parts below, in order
ui/            the page's parts: shared (stores, language), actions (runs,
               revisions, plans continued), sidebar, repositories,
               requirements, plans, tasks (the task window); every visible
               string in Polish and English
```

---

## Documentation

| Document | What it covers |
|---|---|
| [HANDOFF.md](HANDOFF.md) | current state, decisions, backlog and known traps |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the agents, the services, who owns what |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | the pipeline, the review loop, the severity model |
| [docs/REPOSITORY_WORKFLOW.md](docs/REPOSITORY_WORKFLOW.md) | from folder to pull request |
| [docs/SECURITY.md](docs/SECURITY.md) | what the agents may and may not do |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | settings, `.env`, providers |
| [docs/TESTING.md](docs/TESTING.md) | what each suite proves |
| [docs/ROADMAP.md](docs/ROADMAP.md) | what was built, and what each sprint taught |

---

## Known limitations

- **The planner's file claims are checked, its judgement is not.** A plan
  can still split work badly; what it cannot do any more is quietly plan a
  file that exists, or one nothing creates.
