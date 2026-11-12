"""Smoke test for the built executable.

Starts it with an empty stdin: it prints the menu, reaches the end of input and exits.
That is enough to catch a broken bundle: missing modules, plugins that fail to load, a wrong version.

Usage: smoke_test.py --version 1.2.3 <program> [arguments...]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 120  # a one-file executable unpacks itself on the first start
FAILURE_MARKERS = ("Traceback", "was not loaded", "No modules found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="expected application version, for example 1.2.3")
    parser.add_argument("command", nargs="+", help="program to start, followed by its arguments")
    args = parser.parse_args()

    command = list(args.command)
    if Path(command[0]).is_file():
        command[0] = str(Path(command[0]).resolve())

    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, "SPLASHMODIFY_DEBUG": "1"},
        )
    except subprocess.TimeoutExpired:
        print(f"::error::The program did not exit within {TIMEOUT_SECONDS} s")
        return 1

    output = result.stdout.decode("utf-8", errors="replace")
    print(output)

    problems = []
    if result.returncode != 0:
        problems.append(f"exit code {result.returncode}, expected 0")
    if f"v{args.version}" not in output:
        problems.append(f"version v{args.version} not found in the output")
    problems.extend(f"output contains '{marker}'" for marker in FAILURE_MARKERS if marker in output)

    for problem in problems:
        print(f"::error::Smoke test failed: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
