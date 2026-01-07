import math
import shutil

from abc import abstractmethod
from dataclasses import dataclass, field
from dykes import parse_args, StoreTrue
from dykes.options import Flags, NArgs
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, TextArea, Button, Checkbox, Label
from typing import Annotated


SOWPODS = Path(Path(__file__).parent, "data/sowpods.txt")


class Options(VerticalScroll):
    def __init__(self, text_box, args: WGFArgs, wordlist: list[str], id_: str = None):
        super().__init__(id=id_)
        self.text_box = text_box
        self._args = args
        self._wordlist = wordlist
        self._tests = list()
        width, _ = shutil.get_terminal_size((120, 40))
        self._width = math.floor(width * 0.7) - 2

    def compose(self) -> ComposeResult:
        yield from (
            Label("Contains"),
            Input(id="inp-contains", value=" ".join(self._args.contains or [])),
            Label("Starts with"),
            Input(id="inp-starts-with", value=self._args.startswith or ""),
            Label("Ends with"),
            Input(id="inp-ends-with", value=self._args.endswith or ""),
            Label("Contains multiple"),
            Input(id="inp-contains-multiple", value=self._args.multiple or ""),
            Checkbox("Double letters", self._args.double, id="ck-double"),
            Label("Does not contain"),
            Input(
                id="inp-does-not-contain", value=" ".join(self._args.not_contain or [])
            ),
            Label("Minimum word length"),
            Input(id="inp-min-len", type="integer", value=str(self._args.minlen) if self._args.minlen else ""),
            Label("Maximum word length"),
            Input(id="inp-max-len", type="integer", value=str(self._args.maxlen) if self._args.maxlen else ""),
            Button("Update word list", id="btn-submit"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the button press"""
        self.refresh_words()

    def refresh_words(self) -> None:
        self.get_tests()
        self.update_valid_words()

    def on_show(self):
        self.refresh_words()

    def update_valid_words(self):
        self.text_box.text = format_output(
            get_valid_words(False, self._tests, self._wordlist), self._width
        )

    def get_tests(self):
        """Convert the options into Tests"""
        tests = []
        if contains := self.query_one("#inp-contains").value:
            tests.extend(map(Contains, contains.split(" ")))
        if starts := self.query_one("#inp-starts-with").value:
            tests.append(Contains(starts, starts=True))
        if ends := self.query_one("#inp-ends-with").value:
            tests.append(Contains(ends, ends=True))
        if multiple := self.query_one("#inp-contains-multiple").value:
            tests.append(Contains(multiple, multiple=True))
        if self.query_one("#ck-double").value:
            tests.append(Double())
        if not_contains := self.query_one("#inp-does-not-contain").value:
            tests.extend(Contains(c, does_not=True) for c in not_contains.split(" "))
        min_len = self.query_one("#inp-min-len").value or 0
        max_len = self.query_one("#inp-max-len").value or 0
        if min_len or max_len:
            tests.append(Length(int(min_len) or 1, int(max_len) or 1_000_000))
        self._tests = tests


class WordGridTui(App):
    CSS = """
        #txt-valid-words {
            width: 70%
        }
        
        #cnt-options {
            width: 30%
        }   
    """

    BINDINGS = [
        ("ctrl+r", "refresh", "Refresh the word list."),
        ("ctrl+q", "quit", "Exit the Word Grid finder."),
        ("ctrl+c", "copy", "Copy the selected text."),
    ]

    def __init__(self, args: WGFArgs, wordlist: list[str]):
        super().__init__()
        self.text_box = TextArea(id="txt-valid-words", read_only=True, soft_wrap=True)
        self.options = Options(
            self.text_box,
            args,
            wordlist,
            id_="cnt-options",
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon=" ")
        yield Horizontal(
            self.options,
            self.text_box,
        )
        yield Footer()

    def action_refresh(self):
        self.options.get_tests()
        self.options.update_valid_words()

    def action_quit(self) -> None:
        exit()

    def on_mount(self):
        self.title = "Find words for the Word Grid game!"

    def action_copy(self):
        self.copy_to_clipboard(self.text_box.selected_text)


@dataclass
class WGFArgs:
    """Arguments for Word Grid Finder"""

    startswith: Annotated[
        str,
        "Words must start with this substring",
        Flags("-s", "--start"),
    ] = field(default_factory=list)
    endswith: Annotated[
        str,
        "Words must end with this substring",
        Flags("-e", "--end"),
    ] = ""
    minlen: Annotated[
        int,
        "Minimum length of the word",
        Flags("--min"),
    ] = 0
    maxlen: Annotated[
        int,
        "Maximum length of the word",
        Flags("-m", "--max"),
    ] = 0
    contains: Annotated[
        list[str],
        "Substrings that the word must contain",
        NArgs(value="*"),
        Flags("-c", "--contains"),
    ] = field(default_factory=list)
    multiple: Annotated[
        str,
        "Word must comtain multiple instances of the letter",
        Flags("-cm", "--multiple"),
    ] = ""
    double: Annotated[
        StoreTrue,
        "Word must contain the letter as a double letter.",
        Flags("-d", "--double"),
    ] = False
    not_contain: Annotated[
        str,
        "Substrings that the word must not contain",
        NArgs(value="*"),
        Flags("-dc", "--does-not-contain"),
    ] = field(default_factory=list)
    word_list: Annotated[Path, "Path to the word list", Flags("--wordlist")] = SOWPODS


@dataclass
class CLIArgs(WGFArgs):
    reversed: Annotated[
        StoreTrue,
        "Sort from long to short",
        Flags("-r", "--reverse"),
    ] = False
    tui: Annotated[
        StoreTrue,
        "Use the TUI interface",
        Flags("-t", "--tui"),
    ] = False


class Test:
    """Base class for checks"""

    @abstractmethod
    def check(self, word: str) -> bool:
        """Abstract check method"""
        pass


@dataclass
class Contains(Test):
    """Check for words that contain a substring"""

    substring: str  # The substring to check for
    starts: bool = False  # If the substring needs to be at the start of the word
    ends: bool = False  # If the substring needs to be at the end of the word
    multiple: bool = False  # If the substring needs to appear multiple times
    does_not: bool = False  # If the word cannot include the substring

    def check(self, word: str) -> bool:
        if self.starts:
            return word.startswith(self.substring)
        if self.ends:
            return word.endswith(self.substring)
        if self.multiple:
            return word.count(self.substring) > 1
        if self.does_not:
            return self.substring not in word
        return self.substring in word


@dataclass
class Length(Test):
    """Check based on the length of the word"""

    min_len: int
    max_len: int

    def check(self, word: str) -> bool:
        return self.min_len <= len(word) <= self.max_len


@dataclass
class Double(Test):
    """Check for double letters"""

    def check(self, word: str) -> bool:
        import re  # Import here for lazy import since we only need re here.

        return bool(re.search(r"([a-z])\1", word))


def handle_args() -> tuple[list[Test], Path, bool]:
    """Handle the argument parsing"""
    args = parse_args(CLIArgs)
    tests: list[Test] = list()
    if start := args.startswith:
        tests.append(Contains(start, starts=True))
    if end := args.endswith:
        tests.append(Contains(end, ends=True))
    if args.maxlen or args.minlen:
        tests.append(Length(min_len=args.minlen or 1, max_len=args.maxlen or 1_000_000))
    if args.contains:
        tests.extend(map(Contains, args.contains))
    if args.multiple:
        tests.append(Contains(args.multiple, multiple=True))
    if args.double:
        tests.append(Double())
    if args.not_contain:
        tests.extend(
            Contains(substring, does_not=True) for substring in args.not_contain
        )
    return tests, args.word_list, args.reversed


def format_output(wordlist: list[str], line_len: int = 120, separator: str = "\n"):
    """Format the output to columns"""
    if not wordlist:
        return ""
    output = ""
    curr_line = ""
    longest = max(map(len, wordlist)) + 2
    for word in wordlist:
        curr_line += f"{word:>{longest}}"
        if len(curr_line) + longest > line_len:
            output += curr_line + separator
            curr_line = ""
    return output + curr_line


def main():
    """Main function"""
    tests, wordlist, reverse_output = handle_args()
    if not (word_list := wordlist.read_text().splitlines()):
        raise RuntimeError(f"Failed to read word list from {wordlist=}")
    if not tests:
        raise RuntimeError("You didn't specify any constraints!")
    valid_words = get_valid_words(reverse_output, tests, word_list)
    width, _ = shutil.get_terminal_size(
        (120, 40)
    )  # Get the right width for the screen to maaximize output
    print(format_output(valid_words, line_len=width))


def get_valid_words(
    reversed: bool, tests: list[Test], word_list: list[str]
) -> list[str]:
    return sorted(
        (word for word in word_list if all(test.check(word) for test in tests)),
        key=lambda x: (len(x), x),
        reverse=reversed,
    )


def run_tui(args: WGFArgs, wordlist: list[str]):
    WordGridTui(args, wordlist).run()


def start_tui():
    WordGridTui(parse_args(WGFArgs), SOWPODS.read_text().splitlines()).run()


if __name__ == "__main__":
    main()
