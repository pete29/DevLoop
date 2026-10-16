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
