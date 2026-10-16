"""Which npm packages a task's code needs and the repository lacks.

Generated code that imports a library the repository does not
have fails to compile with "cannot find module", and no
rewrite of the code fixes that: the package has to be
installed. That is a fact about the imports and the folder,
so it is found here and offered to a human, never installed
on its own.
"""

import json
import os
import re

# import x from 'a'; import 'a'; export * from 'a';
# require('a'); import('a')
SPECIFIER = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]"""
)

# Node's own modules: no package to install, but TypeScript
# needs @types/node to know them.
NODE_BUILTINS = frozenset(
    {
        "assert", "async_hooks", "buffer", "child_process", "cluster",
        "console", "constants", "crypto", "dgram", "diagnostics_channel",
        "dns", "domain", "events", "fs", "http", "http2", "https",
        "inspector", "module", "net", "os", "path", "perf_hooks",
        "process", "punycode", "querystring", "readline", "repl",
        "stream", "string_decoder", "sys", "timers", "tls",
        "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
        "worker_threads", "zlib", "test",
    }
)

NODE_TYPES = "@types/node"

# A Vitest suite that needs a DOM says so on its first line:
# "// @vitest-environment jsdom". The environment is a
# package like any import, and as missing without it.
ENVIRONMENT = re.compile(r"@vitest-environment\s+([a-z][a-z-]*)")

ENVIRONMENT_PACKAGES = {"jsdom": "jsdom", "happy-dom": "happy-dom"}

# npm's rules for a package name, and nothing else: no
# version, tag, URL, path or git reference can pass, so a
# model cannot name something that is not a registry package.
VALID_NAME = re.compile(r"^(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")

MAX_NAME = 214


def is_valid_name(name: str) -> bool:

    return len(name) <= MAX_NAME and bool(VALID_NAME.match(name))


def package_of(specifier: str) -> str:
    """The package an import names, or "" for a local one."""

    if specifier.startswith((".", "/")) or ":" in specifier and not specifier.startswith("node:"):
        return ""

    if specifier.startswith("node:"):
        return "node:" + specifier[5:].split("/")[0]

    parts = specifier.split("/")

    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) > 1 else ""

    return parts[0]


def imported(contents: list[str]) -> set[str]:
    """Every package the code imports, local paths left out."""

    found = set()

    for content in contents:
        for specifier in SPECIFIER.findall(content):
            name = package_of(specifier)
            if name:
                found.add(name)
        for environment in ENVIRONMENT.findall(content):
            if environment in ENVIRONMENT_PACKAGES:
                found.add(ENVIRONMENT_PACKAGES[environment])

    return found


def declared(repository_path: str) -> set[str]:
    """What package.json depends on, in any section."""

    try:
        with open(os.path.join(repository_path, "package.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)

    except (OSError, ValueError):
        return set()

    names = set()

    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        names |= set((manifest.get(section) or {}).keys())

    return names


def installed(repository_path: str, name: str) -> bool:

    return os.path.isfile(
        os.path.join(repository_path, "node_modules", *name.split("/"), "package.json")
    )


def missing(contents: list[str], repository_path: str) -> list[str]:
    """Packages to install for this code to compile, sorted.

    A package already declared or installed is not missing.
    A Node built-in needs no package, but does need
    @types/node, which a fresh TypeScript project lacks.
    """

    names = imported(contents)

    have = declared(repository_path)

    wanted = set()

    for name in names:

        bare = name[5:] if name.startswith("node:") else name

        if name.startswith("node:") or bare in NODE_BUILTINS:
            wanted.add(NODE_TYPES)
            continue

        wanted.add(name)

    return sorted(
        name
        for name in wanted
        if is_valid_name(name)
        and name not in have
        and not installed(repository_path, name)
    )


def describe_installed(repository_path: str) -> str:
    """The repository's packages, for the Developer's context."""

    have = sorted(declared(repository_path))

    if not have:
        return ""

    return (
        "\nPackages the project has: "
        + ", ".join(have)
        + ". Prefer these and the language's own features. If the "
        "task truly needs another package, import it normally: it "
        "will be offered to a human for installation.\n"
    )
