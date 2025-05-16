"""Additional functions for CLI pretty printing."""

from prompt_toolkit import PromptSession
from prompt_toolkit import print_formatted_text
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML


STYLE = Style.from_dict({
    "prompt": "#00ffcc bold",
    "arrow": "ansiblue",
    "command": "#ffaa00 bold",
    "error": "red",
    "info": "green"
})


def pprint(text: str) -> None:
    print_formatted_text(HTML(text), style=STYLE)


def prompt_session(text: str, session: PromptSession) -> str:
    return session.prompt(HTML(text), style=STYLE)
