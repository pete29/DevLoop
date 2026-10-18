import os

from config.paths import home
from services.llm_provider import (
    LLMProvider,
)


class Settings:

    # =====================
    # AI PROVIDER
    # =====================

    LLM_PROVIDER = LLMProvider.CLAUDE

    # The key comes from ANTHROPIC_API_KEY in .env, never
    # from here.
    CLAUDE_MODEL = "claude-opus-5-5"

    # low | medium | high | xhigh | max. The model's own
    # default is medium; code generation and review are
    # where more effort pays for itself.
    CLAUDE_EFFORT = "high"

    # Per agent, because the calls are not alike. The
    # planner and the architect make a few calls each that
    # decide the shape of everything after them; the
    # developer and QA make one call per file, a dozen a
    # task. Opus where judgement is scarce, Sonnet where
    # volume is. A role missing here uses CLAUDE_MODEL.
    CLAUDE_MODELS = {
        "planner": "claude-opus-5-5",
        "architect": "claude-opus-5-5",
        "developer": "claude-sonnet-5-5",
        "qa": "claude-sonnet-5-5",
    }

    # QA writes tests against code that already passed
    # review; it needs less deliberation than the rest.
    CLAUDE_EFFORTS = {
        "planner": "high",
        "architect": "high",
        "developer": "high",
        "qa": "medium",
    }

    # Dollars per million tokens: input, output, cache
    # read. Used only to report what a task cost; a model
    # missing here is reported in tokens, without a price.
    CLAUDE_PRICES = {
        "claude-opus-5-5": (4.00, 20.00, 0.20),
        "claude-sonnet-5-5": (2.00, 10.00, 0.20),
        "claude-haiku-5-5": (0.10, 0.50, 0.01),
    }

    # Streamed, so a large cap costs nothing unless used.
    # A file cut off at the cap is reported, not written.
    CLAUDE_MAX_TOKENS = 64000

    # A model has to fit the card with its KV cache or it
    # runs half on the CPU. qwen3:8b is 5.2 GB and needs
    # 7.8 GB with a 16k window, against 6 GB of VRAM: 46%
    # of it ran on the processor, at 5.5 tokens a second.
    # This one fits, and measures nine times faster on the
    # same task with no placeholder comments in the output.
    # It writes about half as much per file.
    OLLAMA_MODEL = "qwen2.5-coder:3b"

    OLLAMA_URL = "http://localhost:11434/api/generate"

    OLLAMA_NUM_PREDICT = 8192

    # The context window. Ollama defaults to 4096 when this
    # is not sent, whatever the model supports, and silently
    # drops the front of anything longer. The improve round
    # carries every current file in its prompt, so 4096 is
    # reached as soon as the files hold real code -- and
    # what falls off the front is the task description.
    OLLAMA_NUM_CTX = 16384

    OLLAMA_TIMEOUT = 600

    OLLAMA_THINKING = False

    # =====================
    # DATABASE
    # =====================

    # DEVLOOP_DATABASE points a process elsewhere: the tests
    # run a real worker against a throwaway database, and the
    # worker inherits the variable from whoever started it.
    # Otherwise it sits in the data folder (config/paths.py):
    # the project folder from source, %LOCALAPPDATA%\DevLoop
    # in the exe.
    DATABASE_NAME = os.getenv("DEVLOOP_DATABASE") or os.path.join(home(), "human_in_the_loop.db")

    # =====================
    # WORKFLOW
    # =====================

    # The developer and QA may read repository files the
    # prompt did not show (services/repo_tools.py, #52), this
    # many calls per file. Off unless DEVLOOP_REPO_TOOLS=1:
    # on four eval cases (2026-10-18) it passed the same 4/4
    # for 10% more ($0.1201 against $0.1096) -- worth turning
    # on when a project's missing context is what fails it.
    REPO_TOOLS = (os.getenv("DEVLOOP_REPO_TOOLS") or "0").strip() == "1"

    REPO_TOOL_CALLS = 4

    ENABLE_ARCHITECT = True

    ENABLE_QA = True

    # How many times the Architect may review one task.
    MAX_REVIEW_LOOPS = 3

    # How many fixes the free checks (structure, compile)
    # may ask for before each review. Separate from the
    # reviews: sharing one budget let compile errors use
    # up the rounds the Architect's blockers needed.
    MAX_GATE_FIXES = 2

    # Write the package.json, tsconfig and Vitest config a
    # repository is missing, from templates, before the
    # first task runs. Only ever creates what is absent --
    # an existing file is somebody's and is left alone.
    #
    # Off means the planner is still told not to plan
    # setup tasks, so an empty repository produces code
    # that cannot be built or tested. Leave it on unless
    # the scaffolding is managed elsewhere.
    AUTO_BOOTSTRAP = True

    # Whether the "Run npm install" button exists.
    #
    # Installing reaches the network and runs whatever
    # postinstall scripts the packages carry, which is a
    # different kind of act from anything else here. The
    # approval it requires is the button: nothing installs
    # on its own, during a task, or as part of
    # bootstrapping -- a person presses it, each time.
    #
    # The flag is the second lock, for a machine where
    # that should not be possible at all. Set it False and
    # the button is gone.
    ENABLE_PACKAGE_INSTALLATION = True

    # Ask for the file list first, then write each file in
    # its own call. One call for the whole set makes the
    # model spread one answer's worth of tokens across
    # every file, and it writes stubs: measured against a
    # single call, a file went from ~11 lines to ~50 and
    # the placeholder comments stopped.
    #
    # The cost is wall clock. Each file is its own round
    # trip, so a twelve-file task takes roughly as many
    # minutes. Set this to False to go back to one call.
    GENERATE_FILE_BY_FILE = True

    # How many files one task may produce. Bounds the run
    # time above, and the planning call tends to pad a list
    # it is not given a limit for.
    MAX_FILES_PER_TASK = 12

    # Above this many tasks, a plan suggests splitting its
    # requirement into issues: one pull request per part
    # rather than one for everything. Only a hint; a small
    # requirement stays one branch with a commit per task.
    SPLIT_HINT_TASKS = 6

    # Dollars one plan may spend before a background run
    # stops starting tasks: planning, every attempt and
    # every revision count. 0 means no limit. A task is
    # never cut off midway -- the check is before each one.
    PLAN_COST_LIMIT = 5.0

    # Dollars all plans and tasks may spend in a calendar
    # month (UTC) before nothing more starts: no planning,
    # no task, no revision. 0 means no limit. Set here or as
    # DEVLOOP_MONTH_LIMIT in .env -- the size of the API
    # balance is a good figure.
    MONTH_COST_LIMIT = float(os.getenv("DEVLOOP_MONTH_LIMIT") or 0)

    # The password section of the settings panel. Hidden for
    # now; a password set in .env (python -m services.auth)
    # still guards the page either way.
    PASSWORD_IN_SETTINGS = False

    # A Windows notification when a background run ends:
    # which plan, how it ended, how many tasks wait for
    # approval. No package needed; off here if unwanted,
    # or with DEVLOOP_NOTIFY=0 (the tests set it).
    NOTIFY_ON_RUN_END = os.getenv("DEVLOOP_NOTIFY", "1") != "0"

    # How many model calls of one task may run at once: the
    # developer's files, QA's suites. The first always runs
    # alone to write the prompt cache the rest read. 1 runs
    # them one after another, as before.
    PARALLEL_CALLS = 4

    # How many files one call writes.
    #
    # Batching looks like it should cut the time and does
    # not. A task is slow because of the tokens it has to
    # generate, and the same code is the same tokens
    # whether it arrives in four answers or twelve; all
    # batching saves is re-sending the prompt, which is
    # seconds. What it costs is real: three files to a call
    # made a single call long enough to hit OLLAMA_TIMEOUT,
    # and a timeout then lost three files instead of one.
    #
    # So this stays at 1, where the model is asked for
    # plain TypeScript and JSON is out of the picture
    # entirely. Above 1 it answers in JSON, because one
    # answer then has to carry several files.
    FILES_PER_CALL = 1

    # =====================
    # TEST EXECUTION
    # =====================

    # The only place generated code is executed.
    ENABLE_TEST_EXECUTION = True

    TEST_TIMEOUT = 300

    # How often failing tests may send work back. Each
    # attempt repeats the whole review loop, so this is
    # expensive on a local model.
    MAX_TEST_LOOPS = 1

    # =====================
    # UI
    # =====================

    PAGE_TITLE = "👑 DevLoop"
