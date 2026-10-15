# 👑 DevLoop

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
| Python 3.13 | `langgraph` pulls in `zstandard`, which has no wheel for newer versions yet |
| Node.js 24 LTS | `tsc`, Vitest and `npm install` run inside the generated projects |
| git | branches, commits and pushes in the target repository |
| An Anthropic API key | the default provider |
| A GitHub fine-grained token | optional; issues, push feedback and pull requests |
| A second token with `Administration: write` | optional; only for creating GitHub repositories (`GITHUB_ADMIN_PAT`) |

Ollama and Gemini remain as alternative providers; see
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

# Only when LLM_PROVIDER = GEMINI
GEMINI_API_KEY=
```

Use a **fine-grained** GitHub token scoped to the target repositories only,
with `Contents`, `Pull requests` and `Issues` set to read and write. Without
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
  Architect sees anything, with their own budget (`MAX_GATE_FIXES`).
- The **Architect** reviews design only (coupling, abstractions, SOLID),
  up to `MAX_REVIEW_LOOPS` times. Claims about things a compiler decides are
  filtered out.
- **QA** writes one Vitest suite per source file; after a fix only the
  suites of changed or failing files are rewritten.
- The generated tests are **actually run**. Code that does not compile,
  fails its tests, or never reached the Architect is never recommended.

Each task shows its tokens and cost per agent; the plan shows the cost of
planning.

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

`CLAUDE_PRICES` drives the cost report. `AUTO_BOOTSTRAP` and
`ENABLE_PACKAGE_INSTALLATION` control Step 0; the second removes the
`npm install` button entirely. `SPLIT_HINT_TASKS` (6) is the plan size above
which a split into issues is suggested.

---

## Tests

Each test is a plain script, not pytest. Run them from the project root:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python tests/<name>_test.py
```

There are 30 test files. 26 run offline, against fake transports and
throwaway repositories; `compile_test`, `install_test` and
`test_execution_test` need Node on `PATH`. Four call a real model and are
skipped in routine runs: `architect_test`, `workflow_test`,
`langgraph_test` and `ollama_test` (which needs a local Ollama).

---

## Project structure

```text
agents/        planner, story splitter, developer, architect, QA, test execution,
               git, pull request, issue
workflows/     the orchestrator, the recommendation policy, a LangGraph variant
services/      LLM providers, usage ledger, repository survey, plan validator,
               validation, tsc, Vitest, git, GitHub, plan branches, rollback,
               translations
models/        the data the pipeline passes around
database/      SQLite persistence: repositories, requirements, plans, tasks
tests/         see above
docs/          architecture, workflow, security, configuration, testing, roadmap
app.py         the Streamlit UI (every visible string in Polish and English)
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

- **Review comments left on GitHub don't flow back** to the Developer. In
  the app, a task can be sent back with notes; a comment on the pull request
  cannot yet.
- **No prompt caching yet.** Prompts put the variable part first.
- **Running a whole plan blocks the UI**; there is no worker or queue.
- **A single task outside a plan** is generated on whatever branch is
  checked out.
- **The planner's file claims are checked, its judgement is not.** A plan
  can still split work badly; what it cannot do any more is quietly plan a
  file that exists, or one nothing creates.
