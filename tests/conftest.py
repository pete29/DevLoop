"""pytest's view of the suites: one test per suite script, marked by level.

The suites predate pytest and stay plain scripts, each run in
its own process: several patch modules or settings, and in
one process those patches would leak into the next suite.
Here each script becomes one pytest item, so

    pytest                      every offline suite
    pytest -m unit              one level only
    pytest -n auto              in parallel
    pytest --live               the suites that call the real model too

and a failure shows the checks that failed. Tests written for
pytest itself (tests/e2e/e2e_*.py) are collected the usual way.

"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What each suite exercises. unit: functions and classes on
# their own. integration: real git, SQLite, files, processes
# or the compiler. ui: the real page, rendered headlessly.
# live: the real model -- paid, run by hand.
LEVELS = {
    "unit": {
        "ci_checks_test", "developer_test", "eval_test", "grounding_test",
        "parallel_test", "plan_pull_request_test", "qa_test", "severity_test",
        "structure_test", "translation_test", "version_test",
    },
    "integration": {
        "compile_test", "context_files_test", "context_test", "costs_test",
        "diff_test", "environment_test", "fetch_test", "file_generation_test",
        "git_test", "governance_test", "install_test", "issue_test",
        "orchestrator_test", "packages_test", "plan_branch_test", "plan_runner_test",
        "planner_test", "prompt_cache_test", "pull_request_test", "replay_test",
        "repository_setup_test", "repository_test", "review_feedback_test",
        "schema_test", "structured_review_test", "survey_test", "test_execution_test",
    },
    "ui": {
        "auth_test", "reject_plan_test", "repository_form_test",
        "jobs_view_test", "requirement_form_test", "run_view_test", "settings_test", "standalone_task_test",
    },
    "live": {"architect_test", "ollama_test", "workflow_test"},
}

LEVEL_OF = {name: level for level, names in LEVELS.items() for name in names}

# How much of a failing suite's output to show.
TAIL_LINES = 40


def pytest_addoption(parser):

    parser.addoption("--live", action="store_true", help="also run the suites that call the real model (paid)")


def pytest_configure(config):

    for level, meaning in (
        ("unit", "functions and classes on their own"),
        ("integration", "real git, SQLite, files, processes or the compiler"),
        ("ui", "the real page, rendered headlessly"),
        ("e2e", "a whole path through DevLoop"),
        ("browser", "the real page in a real browser"),
        ("live", "the real model: paid"),
    ):
        config.addinivalue_line("markers", f"{level}: {meaning}")


def pytest_collect_file(parent, file_path):

    if file_path.parent.name == "tests" and file_path.name.endswith("_test.py"):
        return SuiteFile.from_parent(parent, path=file_path)

    return None


class SuiteFile(pytest.File):

    def collect(self):

        name = self.path.stem

        item = SuiteItem.from_parent(self, name=name)

        level = LEVEL_OF.get(name)

        if level is None:
            raise pytest.UsageError(f"tests/{name}.py has no level in tests/conftest.py LEVELS")

        item.add_marker(getattr(pytest.mark, level))

        yield item


class SuiteFailed(Exception):
    pass


class SuiteItem(pytest.Item):

    def runtest(self):

        if self.get_closest_marker("live") and not self.config.getoption("--live"):
            pytest.skip("calls the real model; run with --live")

        environment = {
            **os.environ,
            "PYTHONPATH": ROOT,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }

        command = [sys.executable]


        command.append(str(self.path))

        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            raise SuiteFailed(result.stdout + result.stderr)

    def repr_failure(self, excinfo):

        if not isinstance(excinfo.value, SuiteFailed):
            return super().repr_failure(excinfo)

        lines = str(excinfo.value).splitlines()

        failed = [line for line in lines if line.startswith("FAIL ")]

        return "\n".join(
            (["Failed checks:"] + failed + ["", "Last lines:"] if failed else [])
            + lines[-TAIL_LINES:]
        )

    def reportinfo(self):

        return self.path, None, f"suite {self.name}"
