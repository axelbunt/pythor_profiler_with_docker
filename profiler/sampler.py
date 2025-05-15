"""Handles sampling of a running Python process using LLDB to collect call
stack traces.
"""

import time
from typing import Dict, Union
import psutil
import re
import subprocess
import sys


DEFAULT_SAMPLING_TIMEOUT: float = 0.02  # in seconds


# SAMPLING THREAD BEGIN
##############################
def sample_loop(self) -> None:
    """
    Main sampling loop. Getting a sample every *self.sampling_timeout*
    seconds.

    Loop looks like this:
    1. A permanent LLDB session is started.
    2. while running:
        - Check if tracing process is exist.
        - Suspend thread via LLDB.
        - Capture current running Python function.
        - Resume thread.
        - Sleep for *self.sampling_timeout* milliseconds
    3. Exit LLDB
    """
    self.start_debugger_session()

    while self.running:
        if not psutil.pid_exists(self.pid_to_trace):
            break

        sample = self.get_name_of_running_function()
        self.samples.append(sample)

        time.sleep(self.sampling_timeout)

    self.lldb.stdin.write("detach\n")
    self.lldb.stdin.write("exit\n")
    self.lldb.stdin.flush()

    self.stop()
    sys.exit(0)


def start_debugger_session(self) -> None:
    # Run LLDB and attach to the target process.
    # We use subprocess.Popen to create a permanent interactive session.
    self.lldb = subprocess.Popen(
        ["lldb", "-p", str(self.pid_to_trace), "--local-lldbinit"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Waiting for the LLDB to be ready to obtain new command.
    while True:
        line = self.lldb.stdout.readline()
        if "(lldb)" in line:
            break


def get_name_of_running_function(self) -> Dict[str, Union[float, str]]:
    """
    Capture Python process stack frame and get last function from it (this
    function is currently running).

    1. Interrupts the execution of the target process with
        "process signal SIGINT" command (aka. Ctrl-C).
    2. Executes the `py-bt` command to retrieve the Python stack.
    3. Continues the process execution with the `process continue` command.

    Returns:
        (Dict[str, Union[float, str]]): A dictionary with:
            "timestamp": timestamp of sampling (float)
            "function": name of the currently running function (str)
    """
    timestamp = time.time()
    try:
        # Stop program in LLDB (like Ctrl-C)
        self.lldb.stdin.write("process signal SIGINT\n")
        self.lldb.stdin.flush()
        while True:
            line = self.lldb.stdout.readline()
            if "(lldb)" in line:
                break

        self.lldb.stdin.write("py-bt\n")
        self.lldb.stdin.flush()
        output_lines = []
        while True:
            line = self.lldb.stdout.readline()
            if "(lldb)" in line:
                break

        self.lldb.stdin.write("process continue\n")
        self.lldb.stdin.flush()
        # TODO: understand WTH is going on with this .... stdout??? :>
        # Idk how, but we get `py-bt` output after `continue` command
        # execution.
        while True:
            line = self.lldb.stdout.readline()
            if "(lldb)" in line:
                break
            output_lines.append(line)
        decoded = "".join(output_lines)
        function_name = self.parse_python_stack(decoded)
    except Exception as e:
        print(f"Error capturing sample with lldb: {e}")
        function_name = "Unknown"

    return {"timestamp": timestamp, "function": function_name}


def parse_python_stack(self, py_bt_output: str) -> str:
    """
    Parses the LLDB output of the py-bt command and returns the
    function name, in which the execution is currently in progress.

    Args:
        py_bt_output (str): Output of py-bt program.

    Returns:
        str: Name of Python-function that currently running.
    """
    pattern = re.compile(r'^\s*File "([^"]+)", line \d+, in (.+)$')
    matches = []

    for line in py_bt_output.splitlines():
        m = pattern.search(line)
        if m:
            func = m.group(2).strip()
            matches.append(func)

    if matches:
        return matches[-1]
    return "No function detected."

##############################
# SAMPLING THREAD END
