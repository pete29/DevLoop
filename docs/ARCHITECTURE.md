# Architecture

The platform is a pipeline of agents with a human gate in the middle.
Everything above the gate is advice; everything below it touches your
repository.

## The one rule worth knowing

**Anything that can be decided mechanically is decided in code, not asked
of the model.**

This is not a stylistic preference. It came from watching a local 8B model
approve code with an unbalanced brace, import a file it had never
generated, and report a symbol as undefined that was exported two lines
above. Judgement is left to the model; facts are not.

In practice:

| Decided in code | Left to the model |
|---|---|
| Does this import resolve? | Is this abstraction right? |
| Is this symbol exported? | Is the coupling too tight? |
| Is there a dependency cycle? | Is the naming clear? |
| Does a blocker exist, so what is the recommendation? | What counts as a blocker? |
| In what order do planned tasks run? | How should the epic be split? |
| Which issue does this task serve? | What does the issue actually ask for? |
| Do the generated tests pass? | What should the tests assert? |
| Which file does a path belong to? | What should the file contain? |

---

## Agents

### IssueAgent — `agents/issue_agent.py`

Brings work in from a GitHub backlog and reports back to it. It reads open
issues, turns one into a Requirement, and comments once a pull request
exists.

It never closes an issue. The service can, and there is a button for it,
but nothing in the pipeline calls it: deciding that work is finished is a
human's judgement.

It also files issues the other way, on a human's click: a requirement
written in the app becomes an issue (title and body only), so its plan gets
the issue's branch.

Owns: the link between a backlog and this platform.

### StorySplitter — `agents/story_splitter.py`

Proposes how to split a requirement too large for one pull request into
user stories: vertical slices, each with acceptance criteria, in the
requirement's language. It runs on the planner's model.

It only proposes. A human edits, unticks and confirms the stories in the
app, and only then is each filed as an issue, imported as its own
requirement, and linked under the parent as a GitHub **sub-issue**. Where
sub-issues are not available, the parent gets a task list in a comment
instead. What is checked in code: at least two stories, each titled, no two
the same.

Owns: the shape of a split. Does not own: whether to split, which is a
human's call prompted by `SPLIT_HINT_TASKS`.

### PlannerAgent — `agents/planner_agent.py`

Turns an epic into a list of tasks. The model proposes the breakdown; the
ordering, the dependency checks and the cycle detection happen in code.

It sees the code. Besides what the repository *is* (`repository_context`),
it gets the file listing with each file's exports, and in full the existing
files whose symbols the requirement names (`repository_survey`). Before
this it knew the folder held seven source files and not which, and a second
plan for an issue planned again what the first had built.

Every task declares the source files it **creates** and the existing files
it **modifies**. `services/plan_validator.py` checks those claims against
the folder and the dependency graph, in code:

- a created file must not exist yet — if it does, that part is probably
  done;
- a modified file must exist, or be created by a task it depends on;
- modifying a file another task creates means depending on that task;
- no two tasks create the same file; no test files; no paths outside the
  repository.

Problems are reported on the plan, never repaired: a plan built on a false
assumption is shown to a human, not papered over. The file lists reach the
Developer through the task's prompt (`Create: …`, `Modify: …`).

`PlannerAgent.extend(plan)` continues a plan: the done tasks are listed in
the prompt and kept, new ones are numbered on from them and may depend on
them, unfinished tasks and their executions are replaced
(`PlanRepository.replace_tasks`).

A task may not depend on itself, on a task that does not exist, or sit in a
cycle without being reported: each of those is recorded on the plan and
shown, rather than quietly repaired. A truncated answer keeps the tasks the
model finished rather than being discarded.

Execution is tracked per task — see `models/task_execution.py`. The planner
decides what *may* run; the plan records what *did*.

`Plan.next_ready()` is what a run-all asks between tasks, and `Plan.log()`
and `Plan.running` are what the page draws from. All three read the stored
executions, so a run that is watched and a run that is reopened after a
restart show the same thing.

Owns: what a task *is*.
Does not own: anything about the code that task produces.

### DeveloperAgent — `agents/developer_agent.py`

Writes the source files, one call per file.

Before either, it reads the repository. `repository_survey` walks the
folder and collects what is there with what each file exports — no model
involved, because the filesystem knows. That listing goes into the
planning call, so a task can reuse what an earlier one wrote instead of
inventing it again, and a planned file that already exists is written as
an edit with its current content in hand rather than overwritten blind.

`execute` asks for the file list first — paths and one sentence each, no
code — and then writes each file in its own call, giving the model the
whole list as context so imports line up. `improve` does not regenerate
everything: it works out which files the review is about and rewrites only
those, leaving the rest byte-identical.

Why it is shaped that way is in [CONFIGURATION.md](CONFIGURATION.md) under
**One call per file**: asking for every file in one answer made the model
spread one answer's worth of tokens across all of them and write stubs.

Both fall back to the single-call file set — `Settings.GENERATE_FILE_BY_FILE
= False` does the same deliberately — and that in turn falls back to one
file when the JSON is unusable, because a model that ignores the format
still produces usable code.

A file that cannot be written is skipped and reported rather than failing
the task; the Architect sees a missing file on the next round and says so.
Every file failing does raise, because that is not a partial result.

Before the files leave the agent, `drop_self_imports` cuts any import a
file makes of itself — the one cycle with no design question in it, and the
one a small model writes most often. Every other cycle stays with the
developer, told which edge to remove.

Owns: the content of the files.
Does not own: which files a review is about — that is read out of the
review text by `FileParser.paths_in`, not asked of the model. Nor which
import closes a cycle: `StructureReport.cuts()` decides that.

### ArchitectAgent — `agents/architect_agent.py`

Reviews design: dependency boundaries, the Open/Closed and Single
Responsibility principles, separation of concerns, abstraction quality,
naming, extensibility.

It is **grounded**: the structural validator runs first, its findings are
given to the Architect as already handled, and any claim the Architect
makes about missing files, missing imports, missing symbols, requirement
coverage or compilation is filtered out before it reaches the review.

It is also **stateful**: every review sees the previous rounds and must
classify each earlier finding as resolved or still open.

It answers in a **schema** on Claude (structured outputs, `REVIEW_SCHEMA`):
a score, a recommendation, the resolved findings, and findings each with a
severity, the file it is about and the text. Nothing is parsed out of
prose; a finding about a file names it, so the next round rewrites that
file; the review text in the history and the PR is rendered from the
fields as before. A provider without structured outputs (Ollama)
still answers in the text format, parsed by `review_parser`. The filter on
structural claims (`finding_filter`) stays on both paths, by phrasing.

Owns: whether the design is sound.
Does not own: whether the code compiles.

### Structural validator — `services/structure_validator.py`

Not an agent. A deterministic pass over the generated files that reports:

- a file imported but never generated
- a symbol imported but never exported
- a class used but neither declared nor imported
- a circular dependency
- a requirement from the task with no implementation

Its findings always block, whatever the Architect decided. It understands
`export { X }`, `export * from`, `export default`, folder `index` files,
multi-line imports and parent-relative paths, so those do not produce false
positives.

Owns: whether the file set holds together.

### QAAgent — `agents/qa_agent.py`

Writes one Vitest suite per source file worth testing, as its own file.
Same JSON contract and same single-file fallback as the Developer.

Owns: the tests.

### TestExecutionAgent — `agents/test_execution_agent.py`

Runs the generated Vitest suite and reports what happened. It judges
nothing: the workflow acts on the status.

A failure or a crash sends the files back to the Developer with the test
output. A missing toolchain does not, because rewriting code cannot install
node.

This is the only place the platform executes code it did not write; the
limits are in [SECURITY.md](SECURITY.md).

Owns: whether the generated code actually works.

### GitAgent — `agents/git_agent.py`

Creates the branch, stages exactly the files the task generated, commits,
and — as a separate call — pushes.

**A plan has one branch** (`feature/plan-<id>-<words>`), checked out
*before* each of its tasks is generated, so a task is written against the
code of the tasks before it and committed where that code is. One plan,
one pull request, one commit per task. Tasks commit in the order they ran:
an earlier task on the branch has to be committed or rejected first,
because a later one was generated on top of it. Stacked branches per task
were rejected — a task with two dependencies would need `merge`, and
updating a stacked PR would need `rebase`, both refused by the git allow
list.

A new plan's branch starts from the freshest base that loses nothing:
after a `git fetch`, `origin/main` when somebody merged work the local
`main` never saw, the local `main` when it already contains `origin/main`.
Where it came from is the task's first step, so a stale base is never
mistaken for a fresh one.

**A plan has one pull request, describing the whole plan**: the
requirement, every task with its state, score, compile and test results,
the files and findings of committed tasks, and what they cost. Every push
of the plan's branch rewrites it (title and body only). Opening it is a
human's click; so is merging it, on GitHub — and "Check the PR" reads that
back, which is what moves the requirement to `DELIVERED`.

A task described on its own becomes a plan of one task, so it gets a
plan's branch before generation, cut from the freshest base like any other,
and runs in the background worker.

**Rejecting a task undoes its files** (`services/task_rollback.py`): files
it created are deleted, tracked files it changed are restored from git
with `checkout -- <paths>`, and a file that was there before and git does
not know is left alone. Later tasks on the same branch were built on the
rejected code, and the page says so.

Owns: local and remote git.
Does not own: anything on GitHub beyond the push.

### PullRequestAgent — `agents/pull_request_agent.py`

Opens a pull request for a pushed branch, with a description built from the
run: the task, the score, the findings and the file list. Reuses an
existing pull request for a branch instead of opening a second one.

Owns: the pull request.
Cannot: merge, close, delete or comment — those calls are not reachable.

---

## Orchestration

### Step 0 — the environment

Before a plan's first task, `services/environment_step.py` reads three
facts off disk and out of git — no model: is the scaffolding there, are
TypeScript and Vitest installed, is the scaffolding committed. The plan
shows them as Step 0, one button per missing piece:

1. **Write the scaffolding** from the templates.
2. **npm install** — the one call that reaches the network.
3. **Commit the scaffolding on the base branch**, staged by name, so every
   task branch cut from there has a `package.json`.

Tasks stay disabled until Step 0 is done, because a task run in a folder
that can neither compile nor test spends money on code nothing checks.
A ticked override runs them anyway, visibly. A single task run outside a
plan still scaffolds on its own, and its commit includes what it wrote.

### One task

`workflows/workflow_orchestrator.py` runs one task:

1. Developer writes the files, and they are written to disk.
2. **Free checks first**: the structural validator and the compiler. If
   either fails, the files go straight back to the Developer with their
   findings, and no model is asked to review them.
3. Only a file set that passes both reaches the Architect. A blocker sends
   it back, and the next round starts with the free checks again. At most
   `MAX_REVIEW_LOOPS` rounds; the last one never ends on an unchecked
   revision.
4. QA writes the tests; everything is compiled again and the tests run.
5. On a failure the Developer fixes the code, QA rewrites **only** the
   suites of changed files and of files the failure names, and the free
   checks run again. No second architecture review: a test fix does not
   change the design, and the structural check catches what it could break.
6. A file this run created and later dropped is removed from disk.
7. The diff against git HEAD is computed as review evidence, and the run
   records what it cost (`step.usage`, from `services/usage_ledger.py`).

`WorkflowOrchestrator.revise(task, feedback)` is the same run started from
a task's own files instead of a first draft. A human picks Architect
findings and/or writes notes; the Developer edits the files on disk with
them as blockers, and steps 2–7 follow. The notes are appended to the
task's description ("Human review notes:"), so every later round sees
them, and the review history carries on. The revision is a new task
record; the old one becomes `REVISED`, and the plan points at the new one.

The order is the point. The checks that cost nothing run before the call
that costs most, so the Architect never reviews code a compiler would have
rejected. Code that does not compile, fails its tests, or never reached
the Architect is never recommended for approval.

`workflows/recommendation_policy.py` turns findings into a recommendation.
The model's own recommendation is advisory: a structural finding forces
`REQUEST_CHANGES` regardless, and an absence of blockers forces `APPROVE`
even if the model asked for changes.

### Running a plan — `services/plan_runner.py`

A plan's tasks run in a worker process, not in the Streamlit request. The
page writes a `plan_runs` row (`database/run_repository.py`) and starts
`python -m services.plan_runner <run id>`, detached; the worker runs
`execute_planned` task after task (branch, pipeline, task record,
execution), checks for a stop between tasks, and writes its progress. The
page reads the row and redraws a small fragment every few seconds. The
worker writes only the columns it owns — a whole-row write would undo a
stop the page asked for in the meantime. A dead worker is recognised by its
process (`process_alive`, which on Windows asks rather than signals:
`os.kill(pid, 0)` there terminates the process).

The page is `app.py`, which sets up the session and then calls the parts
in `ui/`: `shared` (the stores, created once per process; the language;
small helpers; the repository list, read again on every run as
`shared.repositories`), `actions` (runs, revisions, continuing a plan —
nothing that draws), `sidebar`, `repositories`, `requirements`, `plans` and
`tasks` (the task window). A LangGraph wiring of the same agents existed
and was removed: only its own test used it.

---

## Services

| Service | Responsibility |
|---|---|
| `structure_validator` | imports, exports, cycles, requirement coverage |
| `review_parser` | the Architect's answer into sections |
| `finding_filter` | drops claims the validator owns, caps review length |
| `file_parser` | a model's JSON into files, through truncation and bad quoting alike |
| `import_repair` | cuts an import a file makes of itself, and says so |
| `repository_survey` | what is already on disk, and what it exports |
| `repository_context` | what the repository *is*: state, tooling, test framework |
| `translations` | every word the interface says, in both languages |
| `package_installer` | the one call that reaches the network, behind a button |
| `type_checker` | whether the project compiles, read-only |
| `bootstrap` | writes the scaffolding a repository is missing, from templates |
| `file_writer` | writes inside the repository, and nowhere else |
| `file_naming` | derives repository paths from the generated code |
| `file_bundle` | renders a file set for prompts and display |
| `test_runner` | runs vitest, reads its summary, under a timeout |
| `git_service` | local and remote git, behind an allow list |
| `git_diff_service` | what the generated files would change |
| `github_service` | the GitHub calls, behind an allow list |
| `github_issue_service` | issues: read, create, link sub-issues, comment, label, close; the parent/child tree |
| `plan_validator` | a plan's file claims against the folder and the dependency graph |
| `repository_setup` | the folder window, and "New repository": GitHub first, then a clone made of allowed git steps |
| `plan_branch` | one branch per plan, or per issue: `feature/issue-<n>-<slug>` |
| `task_rollback` | undoes a rejected task's files; refuses a committed one |
| `usage_ledger` | tokens and dollars per agent, per run |
| `plan_runner` | the background worker: runs a plan's ready tasks, stops on request or failure |
| `review_feedback` | a pull request's review comments, read only; which task a comment is about; comments as revision notes |
| `notify` | a Windows toast when a background run ends, through PowerShell, its text passed as environment variables |
| `ci_checks` | a pull request's check runs and a failed job's log, read only; a failure as revision notes |
| `packages` | which npm packages the code imports and the repository lacks; valid package names |
| `costs` | a task's dollars (stored, or read from an older usage line), a plan's total, a month's, the limit |
| `prompt_cache` | `ask(llm, cached, prompt)`: repeated blocks first, cached by Claude, concatenated for other providers |
| `review_history_formatter` | previous rounds, for the Architect |
| `code_cleaner` | strips fences and reasoning blocks |
| `llm_factory` | picks Claude (per role) or Ollama |

---

## Data

`models/` holds what the pipeline passes around. The two that matter most:

**`Task`** — one run end to end: the description, the generated files, the
review, the findings, the diffs, the commit, the push, the pull request and
the status.

**`Requirement`** — what someone wants built, before it becomes tasks. The
single entry point: typed by hand, or imported from an issue. The planner
reads this and nothing else.

**`Plan`** — a requirement, the tasks the planner carved out of it, and a
`TaskExecution` for each one that has been attempted.

**`TaskExecution`** — one attempt: its status, when it started, when it
ended, the error if it failed, and the `Task` row it produced. A task with
no record has not been attempted, and its status is worked out from the
dependency graph instead. Which tasks are `completed` is derived from these
records rather than stored separately, so the two cannot drift apart.

These persist to SQLite (`database/`). Columns are added by a migration
that runs on startup, so an older database keeps working — a plan saved
before executions existed has its completed list read back as a set of
`COMPLETED` records, and loses nothing.

---

## Where the human sits

```text
Requirement → Requirement → Planner → Developer → Architect ⇄ Validator → QA → Files
                          ↑                          ↓
                          └──── failing tests ── Test Gate
                                                     ↓
                                              Diff Review
                                                     ↓
                                  HUMAN: accept / send back / reject
                                         ↓            ↓
                                         ↓     revise(notes) → back to the Developer
                                         ↓
                                        Commit → Push → Pull Request
```

Nothing below the gate happens without an explicit click, and push and pull
request are separate clicks again. See [SECURITY.md](SECURITY.md) for what
the agents are allowed to do once past it.
