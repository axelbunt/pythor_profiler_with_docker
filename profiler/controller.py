"""Main profiler interface that manages tracing logic and handles commands
from the CLI.
"""

import argparse
from math import sqrt
from tabulate import tabulate
import threading
from typing import List, Set
import psutil
import sys

from .sampler import Sampler, DEFAULT_SAMPLING_TIMEOUT


class ProfilerController:
    def __init__(self):
        self.running = False
        self.functions_to_profile: Set[str] = set()
        self.pid_to_trace: int = 0
        self.sampler_instance: Sampler = None
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
            self.print_results()

        elif args.command == "status":
            self.print_status()

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
        self.sampler_instance = Sampler(
            self.pid_to_trace,
            self.sampling_timeout
        )
        self.sampling_thread = threading.Thread(
            target=self.sampler_instance.start_sample_loop
        )
        self.sampling_thread.daemon = True
        self.sampling_thread.start()

        watcher = threading.Thread(target=self._watch_sampler)
        watcher.daemon = True
        watcher.start()

    def _watch_sampler(self):
        """Wait until sampler is stopped and then stop profiler."""
        self.sampling_thread.join()
        if self.running:
            self.stop()

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

    def print_results(self) -> None:
        """
        Get profiling results and print it in console.
        """
        # TODO: add "(s)" to "Approximate execution time"
        results = {"Function Name": [], "Approximate execution time": []}
        function_counts = {}

        for entry in self.sampler_instance.get_samples():
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

    def print_status(self) -> None:
        """
        Print the following profiler info:
        - Is profiler running.
        - Is PID to trace exists.
        - *self.sampling_thread*
        - *self.sampling_timeout*
        - *self.functions_to_profile*
        """
        print("===Profiler Status===")
        print("Profiler is running." if self.running else
              "Profiler is stopped.")
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
        self.print_results()
