"""Main profiler interface that manages tracing logic and handles commands
from the CLI.
"""

import argparse
from math import sqrt
from tabulate import tabulate
import threading
import time
from typing import List, Set, Dict, Union
import psutil
import re
import subprocess
import sys

from sampler import DEFAULT_SAMPLING_TIMEOUT


class ProfilerController:
    def __init__(self):
        self.running = False
        self.functions_to_profile: Set[str] = set()
        self.samples: List[Dict[float, str]] = []
        self.pid_to_trace: int = 0
        self.sampling_thread: threading.Thread = None
        self.sampling_timeout: float = DEFAULT_SAMPLING_TIMEOUT

    def process_command(self, args: argparse.Namespace) -> None:
        if args.command == "start":
            self.start(pid=args.pid,
                       functions_to_trace=args.func,
                       sampling_timeout=args.timeout)

        elif args.command == "stop":
            self.stop()

        elif args.command == "add":
            self.add_functions_to_profile(args.func)

        elif args.command == "remove":
            self.remove_functions_from_profile(args.func)

        elif args.command == "results":
            self.write_output()

        elif args.command == "status":
            self.status()

        elif args.command == "exit":
            if self.running:
                self.stop()
            sys.exit(0)

        else:
            print("Invalid command.")

    def start(self, pid: int, functions_to_trace: List[str],
              sampling_timeout: float = None) -> None:
        """
        Launch a profiler for the specified process and set of functions with
        selected sampling timeout.

        Args:
            pid (int): PID of process you want to profile.
            functions_to_trace (List[str]): List of functions you want to
                profile in selected Python process.
            sampling_timeout (float): Sampling timeout in seconds. Profiler
                will take a sample of selected Python process one time in
                *sampling_timeout* seconds.
        """
        if self.running:
            print("Profiler is already running!")
            return

        if not psutil.pid_exists(pid):
            print(f"Process PID {pid} not found.")
            sys.exit(0)

        self.running = True
        self.pid_to_trace = pid

        if sampling_timeout is not None:
            self.sampling_timeout = sampling_timeout

        self.add_functions_to_profile(functions_to_trace)
        print(
            f"Starting profiling process {pid} "
            f"for functions: {self.functions_to_profile}"
        )

        # Start collecting samples in a separate thread
        self.sampling_thread = threading.Thread(target=self.sample_loop)
        self.sampling_thread.start()

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

    def add_functions_to_profile(self, func_to_add: List[str]) -> None:
        """
        Add a list of functions for tracing.
        """
        self.functions_to_profile.update(func_to_add)
        print("Sampling functions:", self.functions_to_profile)

    def remove_functions_from_profile(self, func_to_remove: List[str]) -> None:
        """
        Remove a list of functions from tracing.
        """
        self.functions_to_profile.difference_update(func_to_remove)
        print("Sampling functions:", self.functions_to_profile)

    def write_output(self) -> None:
        """
        Get profiling results and print it in console.
        """
        # TODO: add "(s)" to "Approximate execution time"
        results = {"Function Name": [], "Approximate execution time": []}
        function_counts = {}

        for entry in self.samples:
            fn = entry["function"]
            if fn in self.functions_to_profile:
                function_counts[fn] = function_counts.get(fn, 0) + 1

        results = {"Function Name": [], "Approximate execution time": []}

        for fn, count in function_counts.items():
            total_time = count * DEFAULT_SAMPLING_TIMEOUT
            error = sqrt(count) * self.sampling_timeout
            time_with_error = f"{round(total_time, 4)} ± {round(error, 4)}"

            results["Function Name"].append(fn)
            results["Approximate execution time"].append(time_with_error)

        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))

    def status(self) -> None:
        """
        Print the following profiler info:
        - Is profiler running.
        - Is PID to trace exists.
        - *self.sampling_thread*
        - *self.sampling_timeout*
        - *self.functions_to_profile*
        """
        print("===Profiler Status===")
        print("Profiler is running." if self.running else "Profiler is "
              "stopped.")
        print(f"PID {self.pid_to_trace} exists:",
              psutil.pid_exists(self.pid_to_trace))
        print("Sampling thread:", self.sampling_thread)
        print("Sampling timeout:", self.sampling_timeout)
        print("Sampling functions:", self.functions_to_profile)
        print("=====================")

    def stop(self) -> None:
        """
        Stop profiler and print profiling results.
        """
        self.running = False

        print("Profiler stopped.")
        self.write_output()
