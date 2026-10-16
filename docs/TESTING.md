# Testing

## Running them

The tests run under pytest (`pip install -r requirements-dev.txt`, and for
the browser test `python -m playwright install chromium`):

```powershell
pytest -n auto                 # everything offline, in parallel (~30 s)
pytest -m unit                 # one level: unit, integration, ui, e2e, browser
pytest --live                  # also the suites that call the real model (paid)
python tests/coverage.py       # under coverage: a summary and coverage-html/
```

**The levels.** Each test is marked with what it exercises:

| Marker | What it runs against | How many |
|---|---|---|
| `unit` | functions and classes on their own | 11 suites |
| `integration` | real git, SQLite, files, processes or the TypeScript compiler | 27 suites |
| `ui` | the real page, rendered headlessly with Streamlit's AppTest | 7 suites |
| `e2e` | a whole path through DevLoop | 2 tests |
| `browser` | the real page in Chromium (also `e2e`) | 1 test |
| `live` | the real model; skipped unless `--live` | 3 suites |

The suites (`tests/*_test.py`) predate pytest and stay plain scripts:
`tests/conftest.py` collects each one as a single pytest item and runs it in
its own process, because several patch modules or settings that would leak
into the next suite in a shared one. A failing suite reports the checks that
failed. Its level is listed in `LEVELS` in `tests/conftest.py`; a new suite
without one is refused at collection. Tests written for pytest itself live
in `tests/e2e/` and are named `e2e_*.py` (the default `test_*.py` would
import `test_execution_test.py`, and importing a suite runs it).

**Coverage.** `python tests/coverage.py` runs everything under coverage,
every Python subprocess included (each suite's process, the background
worker, the browser test's server), combines the data and prints the
summary; `coverage-html/index.html` has it line by line. At the time of
writing: 80% of 6,676 statements. The full-path e2e test is left out of
the measured run (#42): under coverage its in-process render cannot import
numpy, so `ui/tasks.py`, which it exercises, reads low.

### The end-to-end tests

`tests/e2e/e2e_full_path.py` — a GitHub issue in, a merged pull request out,
clicked through the real page: the issue is imported as a requirement, the
planner plans it, the whole plan runs in the worker's loop, each task is
reviewed and accepted, the branch is pushed, the pull request opened, the
issue told; GitHub merges it, and "Check the PR" reads it back as
DELIVERED. Real: the page, the orchestrator and its checks, git, SQLite,
the HTTP calls with their allow list. Scripted: the model's answers
(`scripted_model.py`; the code is correct, and one file imports
`./days.js`). Faked: GitHub, a server on localhost (`fake_github.py`); the
remote is a bare repository on disk that git reaches through `insteadOf`.
With TypeScript and Vitest borrowed from a sibling project
(`DEVLOOP_TYPESCRIPT_HOME`, or found next to this repository), the real
compiler and test runner check both tasks; without them the environment
step is skipped and the path must still complete.

`tests/e2e/e2e_browser.py` — DevLoop's own server on a free localhost port
against a throwaway database, and Chromium through Playwright: the page
loads with its version, a repository is added by typing its path, a
requirement is written and saved, and the settings switch the language.
It does not press "Choose a folder", which would open a Windows dialog.
Skipped without Playwright's Chromium.

### The old runner

`python tests/run_offline.py` still runs every offline suite, one after
another, with a summary; CI uses it.

Every offline suite at once, each in its own process, with a summary and a
non-zero exit code on any failure:

```powershell
python tests/run_offline.py
```

One suite: as a module, or as a path with `PYTHONPATH` set to the project
root, or the imports will not resolve:

```powershell
python -m tests.severity_test
```

**CI** (`.github/workflows/tests.yml`) runs `tests/run_offline.py` on every
pull request and on every push to `main`, on Windows with Python 3.13 and
Node 24. It has no secrets: the suites fake every model and GitHub call,
and the ones that need a token set a fake one. The three that call a real
model are not run there.

---

## Suites that need nothing

No LLM, no network, no token. They use fake transports and throwaway
repositories, and finish in seconds. This is the set to run before and
after a change.

### `tests.planner_test`

An epic becomes tasks; dependencies decide the order; priority breaks ties.
A cycle is reported rather than looped over, and the tasks caught in it are
kept rather than dropped. A task may not depend on itself or on a task that
does not exist. A truncated plan keeps what the model finished; an
unusable answer fails loudly. Plans survive a restart.

Execution is covered here too: a task is `READY` only when its dependencies
are done, a failure is recorded with its reason and does not unblock what
came after, retrying replaces the record rather than adding a second, and
the dashboard counts agree with the statuses. A plan written before
executions existed still reports its progress after the migration.

Live progress is covered by what the database held *during* a run: the fake
agent reads the plan back from SQLite each time it is called, which shows
task 1 stored as `RUNNING` while it ran and as `COMPLETED` before task 2
began. That is the property the UI depends on, and it cannot be faked by
checking the plan afterwards.

The planner seeing the code is covered against a real folder: the prompt
carries the file listing with exports and, in full, the file whose symbol
the epic names; file paths come back spelled one way; and `PlanValidator`
reports a task that creates an existing file, one that modifies a file
nobody creates, one that modifies another task's file without depending on
it, two creators of one file, a planned test file and a path that escapes
the repository — while a task that waits for its file's creator passes.
File claims survive storage, and reach the Developer in the task's prompt.
Continuing a plan keeps the done task and replaces the failed one, tells the
planner what is done and where to number from, accepts a dependency on a done
task, drops and reports one on nothing, and stores only the executions of
tasks still planned.

One thing is not covered here: the **Stop after this task** button and the
disabled per-task buttons are rendered only while a task is in flight, and
Streamlit's `AppTest` follows every `st.rerun()` to completion, so no
mid-run frame exists to assert against. A failure mid-plan exercises the
same one-task-at-a-time path and is checked instead.

### `tests.issue_test`

Issues are read without pull requests mixed in, commented on and relabelled.
An issue's title and body stay out of reach: a `PATCH` carrying anything but
`labels` or `state` is refused. Closing is possible but never happens while
reporting. An issue becomes a requirement, and re-importing updates rather
than duplicates. Lifecycles are derived, so they cannot drift.

Filing goes the other way: a new issue sends its title and body and nothing
else, and needs a title. A child is linked under its parent by id, and a
link that would take a child from another parent is refused. The issue list
becomes a tree — children after their parent, in number order, a child
whose parent is absent at the top — and a parent reports its progress. A
proposed split drops untitled and duplicate stories, refuses a "split" of
one, and the parent/child texts are pinned.

### `tests.severity_test`

The Architect's answer is parsed from messy real-world shapes: markdown
emphasis, numbered lists, wrapped lines, values on the next line, `None`
and `n/a` meaning empty.

Then the recommendation rules: a blocker requests changes, an absence of
blockers approves, and both override whatever the model said. A finding
cannot be listed as resolved and still open at once.

### `tests.structure_test`

The deterministic pass. A file referenced but never generated, a symbol
imported but never exported, a class used but never declared or imported, a
circular dependency, a requirement with no implementation.

Also the shapes that must **not** produce false positives: `export { X }`,
`export * from`, `export default`, folder `index` files, multi-line
imports, parent-relative paths, and built-ins like `new Error()`.

### `tests.grounding_test`

The boundary between the Architect and the validator. Ten phrasings the
validator owns must be filtered out of a review; eight genuine architecture
findings must survive — including ones that use the same words, like
"Missing abstraction layer" and "Missing logging".

Then the policy: a structural finding outranks the model entirely, even an
explicit `REJECT`.

### `tests.translation_test`

Every key exists in both languages, the two agree about their
placeholders, an unknown key shows itself in brackets rather than
rendering blank, and an unknown language falls back instead of failing.

Then the part that does the real work: it parses `app.py` and every module
in `ui/`, and fails if
any prose is still written literally into a widget. Without it, the next
feature adds an English string nobody notices until a Polish user does.

### `tests.compile_test`

The compiler is never run — its real output is fed in as text. Its
diagnostics become data with a file, a line and a code; a project-wide
error has no file and says so; unrelated chatter parses to nothing.

`FAILED` blocks delivery and `UNAVAILABLE` does not, the same split the
test gate makes. The brief names files and lines, says to change nothing
else, and caps a wall of errors rather than pasting it.

How it is run is checked too: node against the compiler's own
JavaScript, `--noEmit` so it writes nothing, `--pretty false` because
Windows cannot decode the box drawing, never a shell, always in the
repository.

### `tests.install_test`

npm is never run here — the subprocess is faked, so nothing is
downloaded. The switch is checked first and the reason names it; a folder
with no `package.json` has nothing to install. What runs is node against
npm's own CLI with one of two subcommands and two quiet flags, never a
shell, always in the repository and always with a timeout. A lock file
means `ci`. A non-zero exit, a hang and a command that cannot start are
three different reports, and npm's own output is kept and bounded.

### `tests.governance_test`

The safe pull request workflow, asserted rather than described. Every git
command the agents may run and every one they may not; every force and
delete flag refused; a push to `main`, `master` or `develop` refused by
the service rather than merely unused. Staging takes the generated file
and leaves the user's alone. Merging, deleting, editing and approving a
pull request are all outside the allow list, as are deployments and
writing repository contents. Filing an issue is allowed, but never with
assignees or labels, and never without a title.

And the subtle one: closing a pull request through the issues endpoint is
refused, with nothing written while it is established. A governance
document nobody runs is a document that drifts.

### `tests.context_test`

Real folders. An empty one is `EMPTY`, one with code but no tooling is
`BOOTSTRAP_REQUIRED`, and one with the scaffolding is `PROJECT_READY`. A
malformed `package.json` is a state a repository can be in rather than a
crash. A test framework is read from its config file first and the
manifest second.

The sharp one: Jest configured and installed is still not runnable here,
because the gate drives Vitest only — saying otherwise would be a claim
the gate contradicts. Bootstrap writes only what is missing, never over an
existing file, and writes nothing the second time. The planner is checked
to receive the description and the instruction not to plan setup.

### `tests.survey_test`

Real folders on disk, no model. Source and notable config are found;
`node_modules`, builds and `.git` are not. Exports are read so imports can
be checked, and a barrel or a default export is marked unreadable rather
than empty — an import from one must not be called broken. A missing
folder surveys as empty rather than raising.

Then what it is for: an import of a file already in the repository is not
a missing file, a name that file does not export still is, and a file this
task rewrites is judged by its new exports rather than the ones on disk.
The planning call is shown the listing, and a planned file that exists is
written as an edit with its current content.

### `tests.qa_test`

A suite per source file, with the model faked. Type declarations, barrels
and empty files earn no suite; a failed or empty call costs that one suite
and not the rest; every suite failing falls back to the single call. Each
call carries the file it is about and only a listing of the others.

### `tests.developer_test`

How a task becomes files, with the model faked. A plan, then one call per
file, each call carrying the whole plan. One file failing is skipped and
the rest survive; every file failing raises rather than returning nothing.
An unusable plan falls back to the single-call set. A review round rewrites
only the files the review names, adds the ones it says are missing, and
leaves the rest byte-identical — including the case where the review names
no file at all.

A plan that is only the prompt's own example back is treated as no plan,
and an example path mixed into a real plan is dropped — a small model
answers with the illustration it was shown, which is how three unrelated
tasks all produced `src/notification.service.ts`.

Paths are read out of review prose rather than asked for, so that has its
own checks: prose is not mistaken for a path, a bare file name is not one,
and `../../etc/evil.ts` yields nothing. That last one is not hypothetical —
the first version of the pattern started matching after the `../` and
reported `etc/evil.ts`, which is the same path laundering the file writer
already refuses to do.

### `tests.file_generation_test`

A model's JSON becomes files, through fences and surrounding prose. Unsafe
paths are rejected rather than rewritten. A truncated answer keeps the
entries it finished. Files are written, folders created, existing files
overwritten. Rows written before the `CODE` → `source` rename still load.

Cycles have their own set in `tests.structure_test`: the route is kept and
not just the fact, it becomes one instruction naming the import to remove,
the same cycle gives the same instruction twice, and a repeated cycle is
not repeated advice. A file importing itself is cut outright and the cut
is reported; a two-file cycle is left alone, because which edge to drop is
a design decision.

Quoting has its own set. An unescaped quote in generated code must not
cost the file that carries it, and — the harder half — the lenient reader
must not cut a file short at a quote that only looks structural.
`const a = "x", b = 2;`, `parts.join(", ")` and `JSON.parse('{"k": "v"}')`
are all checked to come back whole, because the first attempt at this
truncated every one of them.

### `tests.test_execution_test`

Vitest output parsed from both passing and failing shapes, including
milliseconds. A missing toolchain is `UNAVAILABLE` and does **not** send
work back, while a real failure does. The developer brief carries the
failure text and the tests. Results survive a restart.

The real execution path — installing vitest and running a suite that
passes, then one that fails, then code that will not parse — is exercised
by a scratch suite rather than this one, because it needs npm and a
network.

### `tests.repository_test`

Repository CRUD, the link between a task and its repository, and that both
survive a restart.

### `tests.diff_test`

Added, modified, unchanged and deleted, against real throwaway
repositories. A folder without git is still reviewable. **Generating a diff
changes nothing** — the test captures `git status` and `rev-parse HEAD`
before and after and compares.

### `tests.git_test`

The largest suite. Refused commands and refused `remote` subcommands.
Branch names git would read as flags. Task branches that must not stack:
three tasks, three branches, each one commit on the base, none carrying
another's files.

Then a real branch and commit in a temporary repository, asserting an
unrelated file is left untracked, and a real push to a local bare
repository acting as the remote — a genuine push with no network and no
risk. Finally: no remote configured, no remote-tracking branch, nothing
left the machine.

### `tests.pull_request_test`

The GitHub API is faked. Seven forbidden calls are refused; four allowed
ones work. The token is hidden in error text and nothing is attempted
without one. Remote URLs in both https and ssh form are parsed; non-GitHub
remotes are refused.

Then the gate, the generated description, creation, and that an existing
pull request is reused rather than duplicated. Four failure modes —
authentication, rate limit, missing repository, unreachable — each recorded
without undoing the approval or the push.

---

### The pipeline and the plan's branch

`tests.ci_checks_test` — the Actions jobs of every workflow run of the request's
head commit, failures
first and each marked; a failed Actions job's log, its last 60 lines; a log that
cannot be read falls back to the steps that failed; a failure becomes a note naming
the check; only reads are sent, and re-running, re-requesting, cancelling or
editing a check, or reading checks by branch name, is refused.

`tests.packages_test` — imports are read in every form (static, dynamic,
`require`, re-export), scoped packages by scope and name, local files left
out; missing means neither declared nor installed, and a Node built-in
means `@types/node`; only registry names pass; installing refuses a list
with one bad name without running npm, and runs `install <names> --save
--ignore-scripts`. `tests.orchestrator_test` also checks that a missing
package stops the run with no fix, review, QA or test paid for, and that
checking again after the install uses the same files and goes on to the
review and the tests.

`tests.structured_review_test` — on a provider with structured outputs
the Architect sends `REVIEW_SCHEMA` and the rules with the JSON
instructions (not the text format) as its cached block; the score is
clamped, findings land by severity with their file and empty ones are
dropped, a blocker still decides the recommendation, and the review text
reads as before; every object in the schema forbids extra properties and
requires all its fields; `ClaudeService.generate_json` sends the schema in
`output_config.format` next to the effort.

`tests.standalone_task_test` — the real page, headless, on a throwaway
database: **Generate code** turns the description into a plan of one task
(title and description split as typed) and hands it to a background worker
instead of running it in the page.

`tests.repository_form_test` — the real page, headless: a folder without
git cannot be added until **🌱 Make it a repository** runs `git init`; a
folder inside a repository offers the repository instead.

`tests.requirement_form_test` — the real page, headless: the sidebar lists
only the selected repository's requirements, choosing another repository
for one moves it, switching repository closes it, a save from a page
holding an older copy keeps the move, and a new session starts on the
repository chosen last.

`tests.auth_test` — only a hash is stored and it matches only its
password; with `DEVLOOP_PASSWORD_HASH` set the real page shows nothing but
the sign-in form until the right password, signing out closes it again,
and five failures lock it. The other page tests set the variable empty, so
a password in your own `.env` does not stop them at the form.

`tests.replay_test` — the datepicker run that failed, replayed against a
real compiler: the model's answers scripted as they came (an import of
`./types.js`, a sentence above a suite, a suite an earlier task left
broken), the orchestrator, QA's clean-up and `tsc` real. The task must
compile, be approvable, and cost no fix round. The compiler is borrowed
from a project with TypeScript and Vitest installed
(`DEVLOOP_TYPESCRIPT_HOME`, or a sibling folder that has both) through a
junction; without one, as in CI, it says SKIPPED and passes.

`tests.schema_test` — a new database migrates to the latest version with
every table and column; one from before numbering gains every missing
column with its rows intact and a backup made first; a second open does
nothing; a migration that fails is rolled back and leaves the version
where it was; and three processes migrating one file at once all end at
the latest version.

`tests.run_view_test` — the real page, headless, on a plan whose tasks all
failed in an earlier run and which runs again: the task done in this run
reads COMPLETED, the one under way RUNNING, the one still to come QUEUED,
with no old failure shown.

`tests.parallel_test` — a task's calls answer in the order asked even when
they finish out of order; the first runs alone before any other starts;
then several run at once, never more than `PARALLEL_CALLS`; 1 runs them in
turn; and a failing call is raised, not swallowed.

`tests.version_test` — the version is MAJOR.MINOR.PATCH with a known
stage and an entry in `CHANGELOG.md`; the commit shown beside it is read
from `.git` whether the branch is a loose ref, packed by `git gc` or a
detached HEAD, and left out without a repository.

`tests.settings_test` — `.env` is written one line at a time with every
other line kept, a duplicate definition removed, a key never shown back,
and values that would break the file or are of the wrong kind refused;
on the real page, the panel saves the monthly limit into effect, has no
password section, starts in English and remembers a language chosen.

`tests.reject_plan_test` — the real page, headless, on a real repository:
**🗑 Reject the whole plan** rejects every waiting task after a
confirmation, deletes the files they created, restores the file git knows,
and reopens the tasks in the plan.

`tests.review_feedback_test` — inline comments, review text and the
conversation are read, oldest first, with bare approvals and DevLoop's own
comments left out, and only reads are sent; an inline comment knows its file
and line, becomes a note saying where and who, and goes to the latest record
that wrote its file; writing on a pull request (comments, reviews, edits,
deletes) is refused; a comment sent back is recorded once and not offered
again.

`tests.costs_test` — a task's cost, stored or read from an older usage
line; a plan's total counts planning, failed attempts and every record of
it (revisions and replaced versions too) and nothing of other plans; a
month counts only its own; the limit and its "0 means none"; costs survive
storage, and failed-attempt costs add up in the database rather than in a
copy. `tests.plan_runner_test` also checks that a run stops **before** the
task that would start over the limit, and that a failed attempt's spend
lands on the plan. The history lists every one of the last 30 days, 0 for a quiet one, counts
a plan's own costs on its day, leaves later tasks out, and orders plans by
cost.

`tests.prompt_cache_test` — caching hits only on identical bytes, so that
is what it pins down: the Developer's planning call and every file call open
with the same context block (holding the code the task names), the file
calls share the file list and differ only after it; the Architect sends the
same rules in every review, with nothing of the task in them;
`ClaudeService` marks every cached block with a breakpoint and folds more
than four; a provider that cannot cache gets the same text as one string.

`tests.plan_runner_test` — background runs. A stop the page asks for
survives the worker's writes, and one asked after the end does not reopen
the run. The worker (pipeline faked) runs ready tasks in dependency order,
saves records and executions, honours a stop between tasks, stops at a
failure, and runs one task only when one was asked for. A dead worker is
found by its process; a queued run is left alone. Two runs of one plan are
refused. And a **real worker process** runs against a throwaway database
(`DEVLOOP_DATABASE`) on a plan with nothing left to do, so no model is
called: it records its pid, finishes `DONE` and writes its log. The end of
a run is announced with the plan, the ending and the tasks waiting; the
notification's title reaches PowerShell as a variable, never as script
text; `DEVLOOP_NOTIFY=0` switches it off for every worker these checks
start.

`tests.orchestrator_test` — every agent, the compiler and the test runner
are faked. The free checks run before the Architect; a fix after failing
tests rewrites only the suites it must; a dropped file is removed; each run
reports its cost. And a human's revision: the Developer edits the existing
files rather than starting over, every line of the notes arrives as a
blocker, the files are named when the notes name none, the notes become
part of the task, the checks and review run again with the history carried
on, and what the first attempt created still counts as created.

`tests.plan_branch_test` — one branch per plan, or per issue
(`feature/issue-<n>-<slug>`), checked out before generation; tasks commit
in run order; rejecting deletes created files and restores tracked ones,
is refused on another branch, and is refused for a task already committed.

`tests.plan_pull_request_test` — one pull request per plan: the description
covers the whole plan, labels findings and costs like its checklist, lists
an earlier plan's commits on a shared issue branch, and is rewritten on
every push. A merged request makes the requirement `DELIVERED`.

`tests.fetch_test` — `git fetch` in its one allowed shape, and the base a
new branch starts from: never one that loses work.

`tests.context_files_test` — existing files whose symbols a task names
reach the Developer and the Architect in full, within a budget, tests
excluded.

`tests.environment_test` — Step 0: scaffolding from templates, the install
button, and the scaffolding commit.

`tests.repository_setup_test` — a folder's name becomes the repository's;
a new repository's name and place are checked first; a local-only one is a
repository on `main` with no remote; one "on GitHub" (faked, with a local
bare repository standing in) asks for a private repository with a first
commit, sets `origin`, and leaves `main` tracking `origin/main`. A GitHub
refusal leaves nothing behind. Every other shape of `init` and `remote add`
is refused, and so are templates, teams and organisations for a new
repository.

## The eval

`evals/run_eval.py` runs the cases in `evals/cases.json` through the real
pipeline, each on a fresh copy of `evals/fixture` - a TypeScript project
with a password validator and six rules, so every case builds on existing
code. A case is a task; a task with `install_packages`, which, when it stops
for a missing package, has it installed on the copy and its files checked
again, as the button does; or a `plan`, where the Planner plans a
requirement and every planned task runs in order. It writes
`evals/reports/<date>-<label>.json`: per case,
compile and test results, the Architect's score and verdict, review rounds,
blockers and warnings, files, cost, output tokens and time. A case passes
when it compiles, its tests pass and it is approved. `evals/compare.py`
puts two reports side by side. `tests.eval_test` checks the verdict, the
table and the comparison offline.

It costs money, so it is never part of CI. Run it around any change to a
prompt, a model or an effort; the baseline is
`evals/reports/2026-10-15-baseline-v2.json` (6/6, $0.2454). One run is one
sample: the same task reviewed twice raises different minor findings, so
read a single-case difference as noise until it repeats.

## Suites that call a real model

Minutes rather than seconds, and they spend tokens on the configured
provider (Claude by default), so they are skipped in routine runs:

```powershell
python -m tests.architect_test     # a stateful review with history
python -m tests.workflow_test      # the whole pipeline, one task
python -m tests.ollama_test        # the connection and the model; needs a local Ollama
```

---

## What the tests are for

Three things the offline suites are deliberately good at:

**Proving a limit, not asserting an intention.** "Push cannot force" is a
test that calls `push --force` and expects a refusal, not a comment saying
it should not.

**Proving absence.** The repository with `UNRELATED.md` exists so a test
can assert the file is *not* in the commit. The diff test exists so one can
assert git is *unchanged*.

**Catching the model being wrong.** Several suites feed in an answer that
approves broken code, and assert the system refuses anyway.

---

## When a test fails after a change

Most failures in this project's history were stale assertions, not
regressions: a tab count that grew, a widget selected by index when a field
was added above it, a wording that was reflowed. Read what the assertion
claims before assuming the code broke.

Two that were real, both found this way: task branches stacking on one
another, and a path sanitiser that laundered `../x.ts` into `x.ts`.
