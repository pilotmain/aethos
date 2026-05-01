#!/bin/zsh
# First process is python3, not bash — avoids $BASH_ENV / tset before the script. IDE may still
# run zsh preexec before the command; use ./run_everything.sh start to spawn the host in the background.
D="${0:a:h}"
R="${D}/.."
if [ -x "${R}/.venv/bin/python3" ]; then
  exec "${R}/.venv/bin/python3" "${D}/host_dev_executor_bootstrap.py" "$@"
fi
exec /usr/bin/env python3 "${D}/host_dev_executor_bootstrap.py" "$@"
