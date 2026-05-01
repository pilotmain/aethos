#!/usr/bin/env python3
"""
Exec the bash implementation with a clean environment. Python is the *first* interpreter
(zsh/IDE cannot run tset/reset in preexec *before* Python starts — unlike bash(1) + $BASH_ENV).
Then bash --noprofile --norc runs the real host loop; see _host_dev_executor_impl.sh
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    scripts = Path(__file__).resolve().parent
    impl = scripts / "_host_dev_executor_impl.sh"
    if not impl.is_file():
        print("error: missing " + str(impl), file=sys.stderr)
        sys.exit(1)
    for k in ("BASH_ENV", "ENV", "TERMCAP"):
        os.environ.pop(k, None)
    os.environ["TERM"] = "xterm-256color"
    os.environ.setdefault("SHELL", "/bin/bash")
    # _host_dev_executor_impl.sh re-exec’s into a *second* bash; that second startup can re-trigger
    # tset/reset. After we sanitize the env, one bash is enough.
    os.environ["__OR_HOST_REEXEC__"] = "1"
    argv0 = ["/bin/bash", "--noprofile", "--norc", str(impl), *sys.argv[1:]]
    os.execv("/bin/bash", argv0)
    # unreachable
    assert False


if __name__ == "__main__":
    main()
