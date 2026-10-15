# Roadmap

What has been built, in the order it was built, and what the next step is.

---

## Delivered

### Foundation

| Sprint | What it added |
|---|---|
| 0 | Project skeleton, virtual environment, Ruff, `.gitignore` |
| 1 | Gemini integration and a Streamlit dashboard |
| 2 | SQLite persistence and task history |
| 3 | Architect agent prototype |

### The review loop

| Sprint | What it added |
|---|---|
| 4 | Multi-agent workflow: Developer → Architect → QA |
| 4A | Structured architecture review with a score and a recommendation |
| 4B | **Stateful Architect** — every review sees the previous rounds and must say which findings were resolved |
| 4C | **Severity model** — blockers, warnings and suggestions; only blockers send work back. The recommendation is computed in code, so a lenient model cannot approve broken work |

### Repositories and files

| Sprint | What it added |
|---|---|
| 5A | **Repository awareness** — a task belongs to a real folder |
| 6 | **File generation** — code and tests written to disk, inside the repository and nowhere else |
| 6B | **Multiple files per task** — a file set, not a blob |
| 6C | **Structural validator** — a deterministic pass for broken imports, missing files, undefined symbols, cycles and requirement coverage |
| 6D | **Grounded Architect** — the Architect reviews only what cannot be checked mechanically; its claims about files and imports are filtered out |

### Source control

| Sprint | What it added |
|---|---|
| 7A | **Local git** — an approved task becomes a branch and a commit, staging only its own files |
| 7A.1 | **Diff review gate** — what would change, read from git, before you approve |
| 7B | **Remote push** — one branch, no force, no delete |
| 8 | **Pull requests** — opened with a description built from the run |
| 8.1 | **Documentation** — this set of documents |
| 8.5 | **Test execution gate** — the generated tests are run, and failures send work back |

### Planning

| Sprint | What it added |
|---|---|
| 9 | **Planner agent** — an epic becomes ordered tasks with dependencies and priorities, feeding the existing pipeline unchanged |
| 9.1 | **Requirements workspace** — one place where work is described, and the planner's only input |
| 9.5 | **Execution layer** — every attempt is recorded, failures survive a restart, and a plan reports where it stands |
| 9.5B.1 | **Live progress** — a run-all advances one task per script run, so the dashboard, the log and failures appear while the plan runs |
| 9.6 | **Repository context** — the state of the folder is read before planning, scaffolding is written from templates, and the planner stops inventing setup tasks |
| — | **One call per file** — the Developer plans the file list, then writes each file in its own call; a review round rewrites only what it names |
| 10 | **GitHub issues** — a backlog becomes requirements, and a pull request reports back to the issue it came from |

### The factory (DevLoop)

| Sprint | What it added |
|---|---|
| 11 | **Claude per agent** — Opus where judgement is scarce (planner, architect), Sonnet where volume is (developer, QA); free checks before the paid review; every run says what it cost |
| 11.1 | **Step 0 and one branch per plan** — scaffolding, `npm install` and its commit before any task; a plan's tasks commit in order on one branch; a rejected task's files are undone |
| 11.2 | **One pull request per plan** — its description rebuilt on every push; a merge read back moves the requirement to `DELIVERED` |
| 11.3 | **First live end-to-end run** — push, PR, merge and delivery verified against GitHub; the bugs it found fixed (below) |
| 12 | **The human can say more than yes or no** — a task opens in a window, and can be sent back with chosen findings and the human's own notes |
| 12.1 | **Issues both ways** — a requirement filed as an issue; a large one split into user stories, filed as sub-issues; the issue list as a tree; plans for an issue share `feature/issue-<n>-<slug>` |
| 12.5 | **Background runs** — a plan's tasks run in a worker process; the page reads its progress and console, can stop it between tasks, and notices a worker that died |
| 12.4 | **CI** — the offline suites on every pull request, on Windows, with no secrets; one command runs them locally |
| 12.3 | **Repositories from the file system** — a folder window fills the name and path; "New repository" makes a folder with git and a private GitHub repository as its origin |
| 12.2 | **The planner sees the code** — file listing and exports, referenced files in full; tasks declare what they create and modify; `PlanValidator` checks the claims |

---

## What each sprint actually taught

Worth recording, because the architecture is shaped by these rather than by
a plan:

**4C** — a model that is asked to be helpful will approve code with an
unbalanced brace. Recommendations moved into code.

**6B** — a path sanitiser that *cleans* a dangerous path is worse than one
that rejects it: `../x.ts` became a plausible `x.ts` and got written.

**6C** — the model imported a file it had never generated and approved the
result. Imports, exports and cycles moved into a deterministic pass.

**6D** — once the validator existed, the model started duplicating its
findings and inventing new ones. Responsibility had to be split explicitly,
and the split enforced by filtering.

**7A** — branches were cut from wherever HEAD happened to be, so the second
task branched off the first. Found three sprints later, in a real
repository, by looking at the commit graph.

**9.5** — a failure that is not recorded is a failure that repeats. Before
this, a task that blew up simply reappeared as ready: the UI could not tell
"never tried" from "tried and broke". Deriving `READY`/`PENDING` is right,
because the graph knows them; deriving `FAILED` is impossible, because only
the run knows. Store the attempt, derive the rest.

**The model has to fit the card** — a task took an hour and the reflex was
to blame the pipeline. It was the hardware: 46% of an 8B model was running
on the CPU of a 6 GB laptop, at 5.5 tokens a second, and had been all
along. A model that fits measured nine times faster. Two of the
"optimisations" tried first made it worse — a bigger context window pushed
more of the model onto the CPU, and batching files into one call bought
nothing (the token count is the same either way) while making a single
timeout cost three files instead of one. Measure where the time goes
before changing what produces it.

**9.6** — the planner was asked to decide something it had no way of
knowing. Whether a `package.json` exists is not a judgement, and a model
asked for it answers confidently about a folder it cannot see. The same
line runs through this sprint twice: facts are collected, scaffolding is a
template, and the only thing left for the model is the work the
requirement actually asks for.

**One call per file** — "how much code comes out" turned out to be three
separate problems wearing one coat. A parser that lost a file to an unescaped
quote and said nothing. A review round that returned its input with twenty
characters changed. And a single call asked to write twelve files, which
spends one answer's attention across all of them and writes stubs. Only
the first was a bug; the second and third were the shape of the pipeline.
Telling the model to try harder made it worse — more files, smaller each.
Budget beats instruction.

**9.5B.1** — storing a status is not the same as showing one. `RUNNING` was
already written to SQLite before this sprint, and still nobody ever saw it:
the whole plan ran inside a single script run, so the browser got one frame,
at the end. The fix was not more state but a different shape — persist,
then draw, then work, then rerun. A long loop in a UI thread is a bug
regardless of how good the bookkeeping underneath it is.

**10** — a message pushed into session state is invisible unless something
on screen renders it. The second time this bit: a failure reported from the
sidebar went nowhere, because the only renderer sat inside a task's details.

**8.5** — on Windows, vitest reports failures with characters the default
codepage cannot decode, so the captured output came back empty for exactly
the runs that matter. Found by running a real failing suite, not by reading
the code.

**11.3** — the first live run against GitHub found what no offline suite
had: a task could be rejected after it was committed, which left its
commit, junk test file included, on the branch for the pull request; the
Architect ended a finding with a colon and listed its cases as bullets of
their own, so one warning reached the PR as four; a Polish requirement got
a Polish review, which the English-only finding filter cannot read; and a
commit subject read on from the task's title into its body. Each fix is a
test now.

**12.2** — the second plan for an issue rebuilt what the first had built,
and the only signal was a reviewer noticing. The planner had been given
counts ("seven source files"), never names. Giving it the names was half
the fix; the other half was making it commit to which files each task
touches, so a false assumption is a fact the code can check instead of a
sentence nobody re-reads.

**Across all of them** — the offline test suites caught none of these. Each
came from a real run against a real model.

---

## Next

### Sprint 10 and beyond, unbuilt

```text
PR review feedback      comments left on the pull request on GitHub feeding a revision
Prompt caching          a stable prompt prefix (rules, listing, referenced files) with cache_control
Multi-repository plans  one requirement spanning several repositories
Azure Boards            on hold, by decision: GitHub only for now
```

### Known gaps

**The test gate needs a real JS project.** A repository without
`package.json` and an installed vitest cannot be tested, and the gate says
so rather than pretending.


**The model is the weakest link.** A local 8B model will clear every
structural finding in one round and reintroduce one in the next. The gates
hold and the system refuses to approve, but generation quality is the
model's, not the pipeline's.

**The structural filter is text-based.** Claims the Architect makes about
files and imports are matched against known phrasings. A new wording could
reach the review as noise, though not as a wrong decision.

**Running a whole plan blocks the UI.** Tasks run in sequence in the
browser request; a five-task plan on a local model is a long wait with no
way to stop it part-way.
