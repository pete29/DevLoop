# 👑 Human In The Loop

An AI software factory with a human gate in the middle.

A requirement goes in. AI agents plan it, write it, review it and test it.
A human approves every change. Git and GitHub carry the approved work to a
pull request, and a human merges it.

```text
Requirement (typed by hand, or imported from a GitHub issue)
  → Planner (Opus)              tasks + dependencies, validated in code
  → Step 0: environment         scaffolding, npm install, scaffolding commit
  → per task, on the plan's branch:
      Developer (Sonnet)        one call per file
      Free checks               structural validator + tsc (no model)
      Architect (Opus)          reviews only code that passed the free checks
      QA (Sonnet)               one Vitest suite per source file
      Compile + tests           real tsc, real Vitest
  → Human: accept / reject      accept = commit on the plan's branch
                                reject = the task's files are undone
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

Sidebar → **📦 Repositories** → **➕ Add repository**, with a name and the
path to an existing folder. Point it at a sandbox: generated files overwrite
files whose paths collide, which shows up afterwards in the diff as
`modified`.

### 2. Write a requirement, or import one

**🧠 Requirements** holds a title and a description: user stories,
constraints, acceptance criteria. **📥 GitHub Issues** turns an open issue of
the repository's remote into a requirement; importing it again updates it.

### 3. Plan it

The Planner turns a requirement into tasks with priorities and
dependencies. The ordering, the dependency checks and cycle detection are
computed in code; problems are reported above the plan, never repaired
silently. A task whose dependencies have not finished is blocked.

Every plan gets **one branch** (`feature/plan-<id8>-<slug>`), checked out
before anything is generated. Its base is the freshest point that loses
nothing: local `main` if it already contains `origin/main`, otherwise
`origin/main`.

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

### 6. Accept or reject

**✅ Accept** commits the task's files on the plan's branch, in run order.
**❌ Reject** deletes the files the task created, restores the tracked files
it changed, and reopens the task in the plan so it can run again; tasks that
depend on it wait.

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
`origin/*`), `ls-files`, `merge-base --is-ancestor`, `push`,
`remote get-url`, `rev-parse`, `status`, `symbolic-ref`. `push` may not
force, delete, mirror or push tags, and never targets `main`, `master`,
`develop`, `release` or `trunk`. `pull`, `clone`, `merge`, `rebase`,
`reset`, `tag`, `cherry-pick` and `submodule` are refused. Staging is by
file name, never `git add .`.

**GitHub** is limited to a fixed set of calls matched on method and path.
A `PATCH` on a pull request may carry only `title` and `body`; on an issue
only `labels` and `state`. Merging, closing and deleting are not reachable.

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
`npm install` button entirely.

---

## Tests

Each test is a plain script, not pytest. Run them from the project root:

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python tests/<name>_test.py
```

There are 29 test files. 25 run offline, against fake transports and
throwaway repositories; `compile_test`, `install_test` and
`test_execution_test` need Node on `PATH`. Four call a real model and are
skipped in routine runs: `architect_test`, `workflow_test`,
`langgraph_test` and `ollama_test` (which needs a local Ollama).

---

## Project structure

```text
agents/        planner, developer, architect, QA, test execution, git, pull request, issue
workflows/     the orchestrator, the recommendation policy, a LangGraph variant
services/      LLM providers, usage ledger, repository survey, validation,
               tsc, Vitest, git, GitHub, plan branches, rollback, translations
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

- **The planner is blind to code.** It sees counts, folders and tooling
  state, not files or exports.
- **Pull request review comments don't flow back** to the Developer.
- **No prompt caching yet.** Prompts put the variable part first.
- **Running a whole plan blocks the UI**; there is no worker or queue.
- **A single task outside a plan** is generated on whatever branch is
  checked out.
- **Push, PR creation and merge feedback** have not yet been verified in a
  live end-to-end run.
