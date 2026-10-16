# Changelog

Every release of DevLoop, newest first. Versions follow
[semantic versioning](https://semver.org): before 1.0, the minor number
moves with each release that adds something and the patch number with
fixes. The version lives in `config/version.py` and is shown under the
page title with the commit it was built from.

**How a release is made.** Work goes to `main` as usual and is listed
under *Unreleased* below. When a batch is worth naming:

1. bump `config/version.py` (PATCH for fixes, MINOR for features);
2. rename *Unreleased* to the new version and date, and start a new,
   empty *Unreleased* above it;
3. commit, tag the commit `vX.Y.Z` and push the tag;
4. publish a GitHub Release from the tag, its notes copied from here.

Tags `v*` are protected: a released version cannot be moved or deleted.
There are no release branches; one is cut from a tag
(`git branch release/0.9 v0.9.2`) only if an old line ever needs a fix.

## Unreleased

### Added
- `launcher.py`, the exe's entry point: the page on 127.0.0.1 only, in a
  window of its own (Edge app mode) or a browser tab; a second start opens
  the running one; `--worker <run id>` runs a background run. Data lives in
  `%LOCALAPPDATA%\DevLoop` in the exe and in the project folder from
  source; `DEVLOOP_HOME` overrides both. (#76)
- A first-run page: git, Node.js 18+ and the Anthropic key are checked on
  start, and while one is missing the page says so, with the key's form and
  download links, instead of a run failing on it. (#77)
- `python packaging/build_exe.py` builds `dist/DevLoop/DevLoop.exe`
  (PyInstaller, one folder): DevLoop without a Python setup. The version line
  shows the commit it was built from. (#78)

### Fixed
- What is staged is read from `git diff --cached`: another task's unstaged
  change, first in git's status, read as staged, and accepting a task whose
  work an earlier commit held failed with "nothing added to commit".
  (#65)
- QA no longer reads "a CSV document." in a comment as DOM use: only
  member access on `document`/`window` outside comments counts. The false
  match put jsdom on a Node-only suite, and the run stopped on a missing
  package with every test passing. (#68)
- A run stops at a task that waits for packages, naming them, instead of
  paying for the next task, which fails on the same missing package. A
  result whose tests all pass but where Vitest reported errors says so,
  not "breaks tests (45/45 passed)". (#69)
- A revision's notes reach QA as well as the developer: a wrong test can
  be corrected by a revision instead of by hand. (#70)
- QA extends a suite already on disk instead of writing it again with 3
  tests: earlier tests are kept, and the cap of 3 is for new tests. (#71)
- The developer is told to call what it imports with its real signature,
  never through `as unknown as` or `as any`: a cast hid swapped arguments
  from the compiler. (#74)
- **Check again** stores the files as they are on disk, so the task window
  shows what Accept commits, and a step names the files edited after the
  Architect's review. (#75)

### Changed
- **New repository** asks GitHub, with the everyday token, whether it can
  reach the repository just created, and warns at once if not, instead of
  at the first push. (#73)
- The requirement and plan views name feature branches with commits that
  are not on main, before planning or running: a story built without an
  earlier one's work conflicts with it at merge. `git branch` is allowed
  only to list. (#72)
- An open pull request is asked about when its plan is shown, at most
  once a minute: a merge on GitHub shows without pressing the refresh
  button. (#67)
- Push and the pull request belong to the plan: **Push the branch** and
  **Open pull request** sit in the plan view, for every committed task at
  once, instead of in a task's window. A request already merged is not
  reused: the commits after it get a new one. (#66)

## 0.11.0 (alpha) — 2026-10-16

The factory stops tripping over what the datepicker epic hit. The eval's
four cases from it pass first time: 4/4, $0.1207
(`evals/reports/2026-10-16-datepicker-cases.json`).

### Changed
- The compiler, when it runs, alone judges imports, exports and missing
  files; DevLoop's own structural reading keeps only cycles and the task's
  requirements, and everything where there is no compiler. Its false
  alarms, where tsc passed the code, were most of the datepicker fixes.
  (#62)
- Planning a requirement and revising a task run in the background
  worker, like a plan's tasks: progress and log on the page, untouched by
  clicks, reloads or a closed tab, the result opened when it ends. Two runs
  that write files never share a folder. (#57)

### Tests
- The eval covers what broke on datepicker: an import by the compiled
  name, types through a barrel, DOM code that needs jsdom, a task writing
  an HTML page; a case can set up files in its copy of the fixture. (#63)

## 0.10.0 (alpha) — 2026-10-16

Proven on a real project: the datepicker epic (pete29/datepicker-ts #1),
seven stories from issue to merged pull request on the real model, about
$4 in all, with the factory fixed wherever it fell short on the way.

### Faster
- A task's model calls run side by side: the Developer's files and QA's
  suites, up to `PARALLEL_CALLS` (4) at once. The first call runs alone
  so the others read the prompt cache it writes. Same cost, a task about
  a third faster. (#39)

### Fixed
- A plan run again after every task was rejected starts from the current
  base: its branch, with no commits of its own, is moved up to it instead
  of being checked out on the base it was first cut from. (#44)
- Dollar amounts no longer render as a maths formula: two `$` in one
  message (the run estimate, the month against its limit) were read as
  LaTeX. (#45)
- Step 0 checks that git knows who commits; without `user.name` and
  `user.email` it asks for them for that repository, instead of every
  commit failing. (#46)
- A running plan shows which task runs (RUNNING) and which wait (QUEUED)
  instead of their results from an earlier run, and the page redraws as
  each task finishes. (#47)
- A task is judged only on the tests it broke: the suites run once
  before it, and tests already failing are not its to fix. On datepicker
  every task after the third read FAILED, and paid for a fix round, for
  the third task's two tests. (#48)
- A background run stops at a task whose own tests fail, not only at one
  that does not compile. (#49)
- A revision goes on without a file that has gone from disk since (a
  later task's rejection can remove one), instead of failing at once. (#50)
- QA is shown the repository files the file under test imports, so it
  builds test data from the real types: twice on datepicker it guessed
  `CalendarDate` (a branded string) was an object. (#51)
- A plan's pull request says `Closes #<issue>` once every task is
  committed (`Part of #<issue>` before), so merging it closes the issue
  and the parent's progress counts it. (#53)
- Tests of DOM code get a DOM: QA starts their suite with
  `// @vitest-environment jsdom`, and a task whose tests then need jsdom
  stops and offers the install, as for any package, instead of paying
  for fixes. (#55)
- Barrel files are read: `export type { … } from` counts as an export, and
  QA is shown the file that defines each name imported through a barrel.
  (#58)
- QA writes suites for code only: not for an HTML page or a tool's
  `*.config.*` file. (#59)

### Added
- Review several at once: under a plan's tasks, every task waiting for a
  decision with a checkbox and its facts; Accept checked commits them in
  the plan's order, Reject checked undoes them. Those that can be
  approved are checked already. (#54)
- 🔄 Check again (free) in a task's window: the compiler and the tests once
  more on the files as they are, no model called, the recommendation
  following the facts. (#60)
- A file removed by hand since a task wrote it no longer stops its commit:
  Check again drops it from the task, and the commit stages only files
  that exist or that git knows. (#60)
- A task whose changes an earlier task's commit already holds (both edited
  the same file in the shared folder) is recorded as committed there,
  instead of "nothing to commit" stopping Accept checked. (#61)

### Tests
- pytest runs everything: the suites as one item each in their own
  process, marked `unit`, `integration`, `ui` or `live`; `pytest -n auto`
  in about 30 seconds. (#41)
- `python tests/coverage.py`: coverage of every process the tests start,
  80% of statements. (#41)
- An offline end-to-end test from a GitHub issue to a merged, delivered
  pull request through the real page, the model scripted and GitHub faked
  on localhost. (#41)
- The page in a real browser, through Playwright and Chromium. (#41)

## 0.9.0 (alpha) — 2026-10-15

The first numbered release: everything up to here.

### The factory
- Requirement → plan → tasks → review → pull request → delivery, with a
  human approving every commit, push, pull request and package install.
- Planner (Opus), Developer and QA (Sonnet), Architect (Opus) answering in
  a JSON schema; prompt caching for the blocks that repeat.
- The planner reads the code and declares which files each task creates
  or modifies; the claims are checked against the folder.
- Plans run in a background worker; a desktop notification when one ends.
- Free checks before any review: structure, `tsc`, then Vitest; a task
  is judged only on the type errors it introduced.

### GitHub
- Issues imported as requirements, filed from DevLoop, and a large
  requirement split into sub-issues.
- One branch and one pull request per plan, named after its issue; the
  PR's CI read through the Actions API; review comments sent back for
  revision.

### Working with it
- Repositories picked from the file system or created locally and on
  GitHub; a folder without git is refused with `git init` offered.
- The sidebar shows the selected repository's work and remembers it.
- Send a task back with notes; reject a task or a whole plan, its files
  undone.
- npm packages a task needs are offered for installation, names only.
- Settings in the page: API keys, monthly limit, language (English by
  default). An optional password in front of the page.

### Money
- Cost per task, per plan and per month; a cost history chart.
- A per-plan and a monthly limit; an estimate before running a plan.
- A run stops at the first task that does not compile.

### Under the hood
- Numbered database migrations, with a backup before each upgrade.
- 42 offline test suites in CI, a replay of a failed run against a real
  compiler, and an eval against the real model.
