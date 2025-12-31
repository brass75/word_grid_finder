from abc import abstractmethod
from dataclasses import dataclass, field
from dykes import parse_args, StoreTrue
from dykes.options import Flags, NArgs
from pathlib import Path
from typing import Annotated


SOWPODS = Path(Path(__file__).parent, "data/sowpods.txt")


@dataclass
class WGFArgs:
    """Arguments for Word Grid Finder"""

    startswith: Annotated[
        str,
        "Words must start with this substring",
        Flags("-s", "--start"),
    ] = None
    endswith: Annotated[
        str,
        "Words must end with this substring",
        Flags("-e", "--end"),
    ] = None
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
    ] = None
    reversed: Annotated[
        StoreTrue,
        "Sort from long to short",
        Flags("-r", "--reverse"),
    ] = False
    word_list: Annotated[Path, "Path to the word list", Flags("--wordlist")] = SOWPODS


class Test:
    @abstractmethod
    def check(self, word: str) -> bool:
        """Abstract check method"""
        pass


@dataclass
class Contains(Test):
    substring: str
    starts: bool = False
    ends: bool = False
    multiple: bool = False

    def check(self, word: str) -> bool:
        if self.starts:
            return word.startswith(self.substring)
        if self.ends:
            return word.endswith(self.substring)
        if self.multiple:
            return word.count(self.substring) > 1
        return self.substring in word


@dataclass
class Length(Test):
    min_len: int
    max_len: int

    def check(self, word: str) -> bool:
        return self.min_len <= len(word) <= self.max_len


def handle_args() -> tuple[list[Test], Path, bool]:
    """Handle the argument parsing"""
    args = parse_args(WGFArgs)
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
    return tests, args.word_list, args.reversed


def format_output(wordlist: list[str], line_len: int = 120):
    """Format the output to columns"""
    output = ""
    curr_line = ""
    longest = max(map(len, wordlist)) + 2
    for word in wordlist:
        curr_line += f"{word:>{longest}}"
        if len(curr_line) + longest > line_len:
            output += curr_line + "\n"
            curr_line = ""
    return output


def main():
    tests, wordlist, reversed = handle_args()
    if not (word_list := wordlist.read_text().splitlines()):
        raise RuntimeError(f"Failed to read word list from {wordlist=}")
    if not tests:
        raise RuntimeError("You didn't specify any constraints!")
    print("\n".join(map(repr, tests)))
    valid_words = sorted(
        (word for word in word_list if all(test.check(word) for test in tests)),
        key=lambda x: (len(x), x),
        reverse=reversed,
    )
    print(format_output(valid_words))


if __name__ == "__main__":
    main()
