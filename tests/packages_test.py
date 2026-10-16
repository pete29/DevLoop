"""Offline checks for packages a task's code needs.

npm is never run; its subprocess is faked:

    python -m tests.packages_test
"""

import json
import os
import shutil
import subprocess
import tempfile

from services import package_installer, packages

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


CODE = """
import { z } from "zod";
import type { PasswordRule } from './password-rule';
import * as path from "node:path";
import { scryptSync } from 'crypto';
export { thing } from "@scope/pkg/sub/module";
const lazy = await import("lodash-es");
const old = require('left-pad');
import "./side-effect";
"""

root = tempfile.mkdtemp()

try:

    print("=" * 80)
    print("WHAT THE CODE IMPORTS")
    print("=" * 80)

    check(
        "packages by name, scoped ones by scope and name, local files left out",
        packages.imported([CODE]),
        {"zod", "node:path", "crypto", "@scope/pkg", "lodash-es", "left-pad"},
    )

    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as handle:
        json.dump({"devDependencies": {"typescript": "^5", "vitest": "^2"}, "dependencies": {"lodash-es": "^4"}}, handle)

    os.makedirs(os.path.join(root, "node_modules", "left-pad"))

    with open(os.path.join(root, "node_modules", "left-pad", "package.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")

    check(
        "missing: what is neither declared nor installed; Node's own modules need @types/node",
        packages.missing([CODE], root),
        ["@scope/pkg", "@types/node", "zod"],
    )

    check("a repository with everything needs nothing", packages.missing(["import x from './x';"], root), [])

    check(
        "the developer is told what the project has",
        "lodash-es, typescript, vitest" in packages.describe_installed(root),
        True,
    )

    print()
    print("=" * 80)
    print("ONLY REGISTRY NAMES")
    print("=" * 80)

    for name, ok in (
        ("zod", True),
        ("@types/node", True),
        ("lodash.merge", True),
        ("zod@3.0.0", False),
        ("https://evil.example/pkg.tgz", False),
        ("../evil", False),
        ("git+ssh://github.com/x/y", False),
        ("Zod", False),
        ("--save-dev", False),
        ("", False),
    ):
        check(f"{name!r} {'is' if ok else 'is not'} a package name", packages.is_valid_name(name), ok)

    print()
    print("=" * 80)
    print("INSTALLING: NAMES ONLY, NO INSTALL SCRIPTS")
    print("=" * 80)

    RAN: list[list[str]] = []

    def fake_run(arguments, **kwargs):
        RAN.append(list(arguments))
        return subprocess.CompletedProcess(arguments, 0, "added 1 package", "")

    original_run = package_installer.subprocess.run
    original_cli = package_installer.npm_cli
    original_which = package_installer.shutil.which

    package_installer.subprocess.run = fake_run
    package_installer.npm_cli = lambda: "npm-cli.js"
    package_installer.shutil.which = lambda name: f"C:/node/{name}.exe"

    try:
        refused = package_installer.add_packages(root, ["zod", "evil@1.0.0"])

        check("a list with a non-name is refused whole, npm never run", (refused.succeeded, RAN), (False, []))

        added = package_installer.add_packages(root, ["zod", "@types/node", "zod"])

        check("valid names are installed once each", added.succeeded, True)

        check(
            "with --save and without running the packages' scripts",
            RAN[-1][2:],
            ["install", "@types/node", "zod", "--save", "--ignore-scripts", "--no-audit", "--no-fund"],
        )

    finally:
        package_installer.subprocess.run = original_run
        package_installer.npm_cli = original_cli
        package_installer.shutil.which = original_which

    print()
    print("=" * 80)
    print("A DOM SUITE NEEDS ITS ENVIRONMENT")
    print("=" * 80)

    suite = "// @vitest-environment jsdom\nimport { describe } from 'vitest';\n"

    check("the directive names a package", "jsdom" in packages.imported([suite]), True)

    check("which is missing where it is not installed", "jsdom" in packages.missing([suite], root), True)

    check("happy-dom too", "happy-dom" in packages.imported(["// @vitest-environment happy-dom\n"]), True)

    check("node needs nothing", packages.imported(["// @vitest-environment node\n"]), set())

finally:
    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PACKAGE CHECKS PASSED")
print("=" * 80)
