"""Command-line interface for launching and interacting with the profiler."""

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import WordCompleter

import argparse
import sys

from controller import ProfilerController
from sampler import DEFAULT_SAMPLING_TIMEOUT
from ui_utils import pprint, prompt_session


CLI_COMMANDS = [
    "start", "stop", "add", "remove", "results", "status", "exit"
]


def build_args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Profiler CLI")
    subparsers = parser.add_subparsers(dest="command")

    # TODO: add command to change sampling timeout dynamically
    start_parser = subparsers.add_parser("start",
                                         help="Run profiler with certain "
                                         "arguments.")
    start_parser.add_argument("-p", "--pid", type=int, required=True,
                              help="PID of process you want to profile.")
    start_parser.add_argument("-f", "--func", nargs="+", required=True,
                              help="List of functions you want to profile "
                              "in selected Python process.")
    start_parser.add_argument("-t", "--timeout", type=float,
                              help="Custom sampling timeout. Default is "
                              f"{DEFAULT_SAMPLING_TIMEOUT} s")

    stop_parser = subparsers.add_parser("stop",  # noqa: F841
                                        help="Stop profiler.")

    add_parser = subparsers.add_parser("add",
                                       help="Add functions to profiling.")
    add_parser.add_argument("-f", "--func", nargs="+", required=True,
                            help="List of functions you want to profile "
                            "in selected Python process.")

    remove_parser = subparsers.add_parser("remove",
                                          help="Remove functions from "
                                          "profiling.")
    remove_parser.add_argument("-f", "--func", nargs="+", required=True,
                               help="List of functions you want to remove "
                               "from profiling in selected Python process.")

    results_parser = subparsers.add_parser("results",  # noqa: F841
                                           help="Get intermediate profiling "
                                           "results.")

    status_parser = subparsers.add_parser("status",  # noqa: F841
                                          help="Get profiler status.")

    exit_parser = subparsers.add_parser("exit",  # noqa: F841
                                        help="Exit Profiler CLI.")

    return parser


def run_cli_loop() -> None:
    profiler = ProfilerController()
    parser = build_args_parser()

    command_completer = WordCompleter(CLI_COMMANDS, ignore_case=True)
    session = PromptSession(completer=command_completer)

    pprint("<ansicyan>\n🚀 Welcome to <b>Sample Profiler CLI</b>! "
           "Type <b>help</b> or <b>exit</b> to quit.\n</ansicyan>")

    if len(sys.argv) > 1:
        args = parser.parse_args()
        profiler.process_command(args)

    while True:
        try:
            with patch_stdout():
                command_line = prompt_session(
                    "<arrow>➤ </arrow><prompt>Profiler</prompt>"
                    "<arrow> > </arrow>",
                    session
                ).strip()

            if not command_line:
                continue

            args = parser.parse_args(command_line.split())
            profiler.process_command(args)
        except SystemExit as e:
            if e.code != 0:
                pprint("<error>⚠️ Invalid command. Type -h for help.</error>")
            else:
                # TODO: resolve minor bug, after command exit statistics
                # prints two times
                pprint("\n<info>👋 Exiting Profiler CLI. Bye!</info>")
                return
        except KeyboardInterrupt:
            pprint("<error>\n🛑 Interrupted. Use 'exit' or Ctrl+D to quit."
                   "</error>")
        except EOFError:
            pprint("\n<info>👋 Exiting Profiler CLI. Bye!</info>")
            return
        except Exception as e:
            pprint(f"<error>💥 Error: {e}</error>")


if __name__ == "__main__":
    run_cli_loop()
