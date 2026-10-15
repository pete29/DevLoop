# Changelog

Every release of DevLoop, newest first. Versions follow
[semantic versioning](https://semver.org): before 1.0, the minor number
moves with each release that adds something and the patch number with
fixes. The version lives in `config/version.py` and is shown under the
page title with the commit it was built from.

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
