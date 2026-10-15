# Repository workflow

What happens to the files, from the moment you pick a folder to the moment
a pull request exists.

---

## 1. Selecting a repository

Sidebar → **📦 Repositories** → **➕ Add repository**. **📁 Choose a
folder…** opens the system's folder window (the app runs on your machine)
and fills the path and the name — the folder's own. A typed path fills the
name too. The repository added becomes the selected one.

- The folder must already exist; this panel does not create it.
- It does not have to be a git repository. Generation works either way; the
  commit, push and pull request stages need one.
- The same folder cannot be registered twice.
- A task creation is blocked until a repository is selected.

**🆕 New repository** creates one: a folder with git on `main` and, by
default, a private GitHub repository set as its `origin`, ready for plans,
pull requests and issues. GitHub goes first and creates the repository with
a first commit, so `main` exists and a pull request has a base; the local
side is then `init`, `remote add origin`, `fetch` and a checkout of `main`
(a clone made of allowed steps — `clone` itself is refused). If GitHub
refuses, nothing is left behind locally. Creating a repository needs a
token with `Administration: write`: `GITHUB_ADMIN_PAT` is used when set, so
the everyday `GITHUB_PAT` keeps its narrow scope.

Removing a repository asks for confirmation when tasks are linked to it,
and says how many. Removal does not delete those tasks: each one also
stores the **path** it wrote to, so re-adding the same folder reconnects
them, and their files stay readable even while it is unregistered.

---

## 2. Generating files

The Developer returns a file set as JSON. Each path is validated before
anything is written:

- rejected: `..` in any segment, absolute paths, drive letters, control
  characters, empty segments
- rejected, not repaired: stripping the dangerous part of `../x.ts` would
  turn it into a legitimate-looking `x.ts` that then gets written
- normalised: a leading `./`, Windows separators

Paths are then resolved against the repository root and checked again, so a
path that survives validation still cannot escape the folder.

Where the files land is derived from the code itself:

| Generated code | Path |
|---|---|
| `export class NotificationService` | `src/services/notification.service.ts` |
| `export class EmailValidator` | `src/validators/email.validator.ts` |
| `export interface Notifier` | `src/notifier.ts` |
| a file declaring many classes | named after the task, e.g. `src/notification-system.ts` |

Tests go to `tests/<same stem>.test.ts`.

Existing files are **overwritten**. That is visible afterwards in the Diff
Review tab as `modified`, but it is a reason to point this at a sandbox
rather than at work you care about.

---

## 3. Reviewing the diff

Before you approve, the Diff Review tab shows what the generated files
would change **in git terms**, not on disk. The files are already written
by the time you look, so the disk is not a baseline; git HEAD is.

| Verdict | Meaning |
|---|---|
| `added` | git has never seen this file |
| `modified` | it differs from the committed version |
| `unchanged` | identical to what is committed |
| `deleted` | the task claims a file that is not on disk |

The whole pass is read-only. A test asserts that generating a diff leaves
the working tree and HEAD untouched.

Without git there is no baseline, so every file reads as `added` and the
gate still works.

---

## 4. Committing

**A plan has one branch**, checked out before its first task is generated:
`feature/plan-<id8>-<slug>`, or `feature/issue-<number>-<slug>` for a plan
made from a GitHub issue. Every plan for the same issue shares that branch.
The second task is written next to the first task's files and committed on
top of them, so a plan is a chain of commits, one per task, in run order.

**The branch starts from the freshest base that loses nothing.** After a
`git fetch` of `origin` (the one fetch the allow list permits): local
`main` if it already contains `origin/main`, otherwise `origin/main` — so a
merged pull request is the starting point of the next plan. With no remote
or no connection, local `main`, and the task says so.

Approval commits on that branch. A task outside a plan is committed on a
`feature/task-<id8>` branch of its own.

**Only the files this task generated are staged.** Not `git add .`. Work
in progress elsewhere in your repository is left alone, and a test proves
it by keeping an unrelated file in the repository and asserting it never
reaches the commit.

The commit subject is the task's title (`feat: utwórz regułę cyfry`); the
body carries the task, the architecture score, the recommendation and the
file list.

**Rejecting** deletes the files the task created and restores the tracked
files it changed (`git checkout -- <paths>`). A task that is already
committed cannot be rejected: that would leave its commit on the branch.
Fix it with another task, or send a task back for revision before
accepting it.

---

## 5. Pushing

A separate click. It validates first:

- a local commit exists
- the folder is a git repository
- a remote named `origin` is configured

The push sends one branch, fully qualified
(`refs/heads/x:refs/heads/x`), so it can only create or fast-forward. Force,
delete, mirror, tags and `--all` are refused, and so is any push to `main`,
`master`, `develop`, `release` or `trunk`.

A failure records why and changes nothing else: the approval stands, the
local commit stands, and you can retry.

---

## 6. Opening a pull request

Another separate click, needing `GITHUB_PAT` in `.env`.

**One pull request per plan** (per issue, when plans share its branch). The
base is the repository's default branch, read from the GitHub API rather
than assumed. If a pull request already exists for the branch, it is reused
rather than duplicated.

The description covers the whole plan: the requirement, a checklist of its
tasks with their state and commit, score, compile and test results, the
files, findings and cost of committed tasks — and what an earlier plan
committed on a shared issue branch. **Every later push rewrites it**, so it
never describes one task of five.

You merge on GitHub — a merge commit keeps one commit per task. **🔄 Check
the PR** reads the merge back and moves the requirement to `DELIVERED`.
When the work came from an issue, the issue gets a comment with the pull
request; it is never closed automatically.

A failure records why — authentication, rate limit, missing repository,
network — and leaves the push and the approval untouched.

---

## What this looks like in a repository

A plan of three tasks for issue #4, and a small plan without an issue:

```text
main
 ├── feature/issue-4-reject-common-passwords
 │     ├── feat: create the blocklist rule        task 1
 │     ├── feat: add the built-in password list   task 2
 │     └── feat: export the blocklist             task 3
 └── feature/plan-e64d93f0-walidator-hasel
       └── ... one commit per task
```

One branch and one pull request per plan, a commit per task. A requirement
too large for one pull request is split into issues first, and each issue
gets its own branch.
