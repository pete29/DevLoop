"""Builds DevLoop.exe with PyInstaller.

    pip install -r requirements-dev.txt
    python packaging/build_exe.py

The result is dist/DevLoop/: DevLoop.exe and the files it
needs beside it. One folder rather than one file: a one-file
exe unpacks itself on every start, and every background run
starts the exe again (DevLoop.exe --worker <id>), so each run
would pay for the unpacking too. Zip the folder to hand it on.

The page is run by Streamlit as a script, so PyInstaller does
not see what it imports: DevLoop's packages are collected
whole, and Streamlit's static files and metadata with them.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)

PACKAGES = ("agents", "config", "database", "models", "services", "ui", "workflows")

BUILD_FILE = os.path.join(ROOT, "config", "build_commit.py")


def head() -> str:
    """The commit being built, for the version line in the exe."""

    try:
        return subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    except (OSError, subprocess.CalledProcessError):
        return ""


def arguments() -> list[str]:

    separator = os.pathsep

    found = [
        os.path.join(ROOT, "launcher.py"),
        "--name=DevLoop",
        "--onedir",
        # DevLoop's own window (launcher.py), no console:
        # the server's log goes to launcher.log.
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--distpath={os.path.join(ROOT, 'dist')}",
        f"--workpath={os.path.join(ROOT, 'build')}",
        f"--specpath={os.path.join(ROOT, 'build')}",
        f"--add-data={os.path.join(ROOT, 'app.py')}{separator}.",
        "--collect-all=streamlit",
        "--copy-metadata=streamlit",
        "--collect-submodules=anthropic",
        "--collect-all=webview",
    ]

    for package in PACKAGES:
        found.append(f"--collect-submodules={package}")

    return found


def main() -> int:

    try:
        import PyInstaller.__main__ as pyinstaller

    except ImportError:
        print("PyInstaller is not installed: pip install -r requirements-dev.txt")
        return 1

    with open(BUILD_FILE, "w", encoding="utf-8") as handle:
        handle.write(f'"""Written by packaging/build_exe.py."""\n\nCOMMIT = "{head()}"\n')

    try:
        pyinstaller.run(arguments())

    finally:
        os.remove(BUILD_FILE)

    exe = os.path.join(ROOT, "dist", "DevLoop", "DevLoop.exe")

    print(f"Built: {exe}" if os.path.isfile(exe) else "The build did not produce DevLoop.exe.")

    # PyInstaller's own scratch; the result is in dist/.
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)

    return 0 if os.path.isfile(exe) else 1


if __name__ == "__main__":

    sys.exit(main())
