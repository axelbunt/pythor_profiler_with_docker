"""Sampler interface that handles sampling of a running Python process using
LLDB to collect call stack traces.
"""

import time
from typing import List, Dict, Union
import psutil
import re
import subprocess


DEFAULT_SAMPLING_TIMEOUT: float = 0.02  # In seconds


class Sampler:
    def __init__(self, pid_to_trace: int, sampling_timeout: float):
        self.pid_to_trace = pid_to_trace
        self.sampling_timeout = sampling_timeout
        self.is_running = False
        self.samples: List[Dict[float, str]] = []
        self.lldb_instance = None

    def start_sample_loop(self) -> None:
        """
        Start main sampling loop. Getting a sample every
        *self.sampling_timeout* seconds.

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
        self.is_running = True
        self.start_debugger_session()

        while self.is_running:
            if not psutil.pid_exists(self.pid_to_trace):
                break

            sample = self.get_name_of_running_function()
            self.samples.append(sample)

            # TODO: make async?
            time.sleep(self.sampling_timeout)

        self.lldb_instance.stdin.write("detach\n")
        self.lldb_instance.stdin.write("exit\n")
        self.lldb_instance.stdin.flush()

        return

    def start_debugger_session(self) -> None:
        # Run LLDB and attach to the target process.
        # We use subprocess.Popen to create a permanent interactive session.
        self.lldb_instance = subprocess.Popen(
            ["lldb", "-p", str(self.pid_to_trace), "--local-lldbinit"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Waiting for the LLDB to be ready to obtain new command.
        while True:
            line = self.lldb_instance.stdout.readline()
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

        # TODO: add check to process stop:
        # (lldb) [1]  + 16568 done       python3 main.py
        # Process 16568 exited with status = 0 (0x00000000)

        try:
            # Stop program via LLDB
            self.lldb_instance.stdin.write("process signal SIGINT\n")
            self.lldb_instance.stdin.flush()
            while True:
                line = self.lldb_instance.stdout.readline()
                if "(lldb)" in line:
                    break

            self.lldb_instance.stdin.write("py-bt\n")
            self.lldb_instance.stdin.flush()
            output_lines = []
            while True:
                line = self.lldb_instance.stdout.readline()
                if "(lldb)" in line:
                    break

            self.lldb_instance.stdin.write("process continue\n")
            self.lldb_instance.stdin.flush()
            # TODO: understand WTH is going on with this .... stdout??? :>
            # Idk how, but we get `py-bt` output after `continue` command
            # execution. Maybe we should make continue after attaching or make
            # sample and continue.
            while True:
                line = self.lldb_instance.stdout.readline()
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

    def get_samples(self) -> List[Dict[float, str]]:
        return self.samples
