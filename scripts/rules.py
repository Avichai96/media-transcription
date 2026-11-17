"""Check the rules ruff and pylint lack; `uv run format` runs it after them.

FF001: a function in a router, service, worker, task or client that awaits has a
try/except, which turns what it catches into its own layer's error.
FF002: an except in those files raises, re-raises or logs, and never swallows.
FF003: a function outside any class and without a decorator has a reason, which
commits/<developer>/<date>.md keeps; in a terminal, it asks the developer for one.
"""

import ast
import getpass
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# FF003 checks the code in these; tests and Alembic's revisions are left to their tools.
CHECKED_DIRS = ("src", "scripts", "lambdas", "migrations")
SKIPPED_DIRS = ("migrations/versions",)
# The layers that do I/O, which FF001 and FF002 check under src/.
LAYER_FILES = frozenset(
    ("router.py", "service.py", "worker.py", "task.py", "client.py"),
)
# A called method of this name logs, so an except that calls it doesn't swallow.
LOG_METHODS = frozenset(("exception", "error", "warning", "critical"))
REASONS_DIR = ROOT / "commits"
# Each reason is a section whose heading names its function by path and name.
HEADING = re.compile(r"^## `(?P<key>[^`]+::[^`]+)`$", re.MULTILINE)
MIN_REASON_LENGTH = 10
NOQA = re.compile(r"#\s*noqa:\s*(?P<codes>[A-Z0-9, ]+)")

type FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
# The nodes that open a scope of their own, whose bodies are not their parent's.
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


@dataclass(frozen=True)
class Violation:
    """One broken rule at one line of one file.

    It prints as ruff's concise output does, so editors can jump to it.
    """

    path: str
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


@dataclass(frozen=True)
class ModuleFunction:
    """A function outside any class and without a decorator.

    Its key, path::name, is the heading of its reason in commits/.
    """

    path: str
    line: int
    name: str

    @property
    def key(self) -> str:
        return f"{self.path}::{self.name}"


class SourceFile:
    """One Python file, parsed, with the functions each rule looks at.

    A file that doesn't parse has none, since ruff already reports it.
    """

    def __init__(self, path: Path) -> None:
        self.relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        self.lines = text.splitlines()
        try:
            self.tree: ast.Module | None = ast.parse(text, filename=self.relative)
        except SyntaxError:
            self.tree = None

    @property
    def is_layer(self) -> bool:
        name = Path(self.relative).name
        return self.relative.startswith("src/") and name in LAYER_FILES

    def violations(self) -> list[Violation]:
        """Return the FF001 and FF002 violations of a layer file."""
        if self.tree is None or not self.is_layer:
            return []
        found = [
            Violation(
                self.relative,
                node.lineno,
                "FF001",
                f"{node.name} awaits without a try/except; catch what it can "
                "raise and raise this layer's own error from it",
            )
            for node in self._definitions(self.tree)
            if self._is_public(node.name)
            and self._awaits(node)
            and not self._catches(node)
            and not self._silenced(node.lineno, "FF001")
        ]
        found += [
            Violation(
                self.relative,
                node.lineno,
                "FF002",
                "this except swallows the error; raise this layer's error "
                "from it, re-raise it, or log it",
            )
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ExceptHandler)
            and not self._raises_or_logs(node)
            and not self._silenced(node.lineno, "FF002")
        ]
        return found

    def module_functions(self) -> list[ModuleFunction]:
        """Return the functions outside any class that have no decorator."""
        if self.tree is None:
            return []
        return [
            ModuleFunction(self.relative, node.lineno, node.name)
            for node in self._module_level(self.tree.body)
            if not node.decorator_list
        ]

    def _definitions(self, node: ast.Module | ast.ClassDef) -> Iterator[FunctionNode]:
        # The functions of the module and the methods of its classes, not closures.
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                yield child
            elif isinstance(child, ast.ClassDef):
                yield from self._definitions(child)

    def _module_level(self, body: list[ast.stmt]) -> Iterator[FunctionNode]:
        # Also the functions under a module-level if, try or with, as TYPE_CHECKING has.
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                yield node
            elif isinstance(node, ast.If | ast.Try | ast.TryStar | ast.With):
                for block in ("body", "orelse", "finalbody"):
                    yield from self._module_level(getattr(node, block, []))
                for handler in getattr(node, "handlers", []):
                    yield from self._module_level(handler.body)

    def _silenced(self, line: int, code: str) -> bool:
        match = NOQA.search(self.lines[line - 1])
        return match is not None and code in re.split(r"[, ]+", match["codes"])

    @classmethod
    def _own_nodes(cls, node: ast.AST) -> Iterator[ast.AST]:
        # The nodes of a function's own body, not those of a function or class in it.
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, SCOPES):
                yield child
                yield from cls._own_nodes(child)

    @staticmethod
    def _is_public(name: str) -> bool:
        return not name.startswith("_") or name == "__call__"

    @classmethod
    def _awaits(cls, node: FunctionNode) -> bool:
        return any(
            isinstance(child, ast.Await | ast.AsyncWith | ast.AsyncFor)
            for child in cls._own_nodes(node)
        )

    @classmethod
    def _catches(cls, node: FunctionNode) -> bool:
        return any(
            isinstance(child, ast.Try | ast.TryStar) and child.handlers
            for child in cls._own_nodes(node)
        )

    @classmethod
    def _raises_or_logs(cls, handler: ast.ExceptHandler) -> bool:
        return any(
            isinstance(node, ast.Raise)
            or (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in LOG_METHODS
            )
            for statement in handler.body
            for node in (statement, *cls._own_nodes(statement))
        )


class Reasons:
    """The reasons in commits/<developer>/<date>.md for FF003's functions.

    ask() asks in the terminal, since git gives pre-commit no stdin, and saves each
    answer under the developer's git user.name and today's date.
    """

    def __init__(self) -> None:
        self.keys = {
            match["key"]
            for path in REASONS_DIR.glob("*/*.md")
            for match in HEADING.finditer(path.read_text(encoding="utf-8"))
        }
        self.saved: list[Path] = []

    def ask(self, function: ModuleFunction) -> bool:
        """Ask why function is outside a class, and save the answer; False if none."""
        today = datetime.now(UTC).astimezone()
        path = REASONS_DIR / self._developer() / f"{today:%Y-%m-%d}.md"
        question = (
            f"{function.path}:{function.line}: {function.name} is outside any class "
            "and has no decorator.\nWhy is it written that way? The answer goes in "
            f"{path.relative_to(ROOT)}; leave it empty to stop.\n> "
        )
        while True:
            answer = (self._input(question) or "").strip()
            if not answer:
                return False
            if len(answer) >= MIN_REASON_LENGTH:
                break
            question = f"Give at least {MIN_REASON_LENGTH} characters.\n> "
        self._save(path, function, answer)
        return True

    def stage(self) -> None:
        """Stage the saved reasons, so a function's commit carries its reason."""
        if not self.saved:
            return
        try:
            subprocess.run(
                ["git", "add", "--", *map(str, self.saved)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
        except OSError:
            # Without git there is nothing to stage; the files are still written.
            print("git not found; commit", *self.saved, file=sys.stderr)

    def _save(self, path: Path, function: ModuleFunction, reason: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        title = "" if path.exists() else f"# Module-level functions, {path.stem}\n"
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{title}\n## `{function.key}`\n\n{reason}\n")
        self.keys.add(function.key)
        if path not in self.saved:
            self.saved.append(path)

    @staticmethod
    def _developer() -> str:
        # git's user.name names the developer's directory, or else the login name.
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            name = result.stdout.strip()
        except OSError:
            name = ""
        if not name:
            try:
                name = getpass.getuser()
            except OSError:
                name = "unknown"
        # One safe path component: no separator, and no leading dot, so never "..".
        return re.sub(r"[^\w.-]+", "-", name).strip("-.") or "unknown"

    @staticmethod
    def _input(question: str) -> str | None:
        # The terminal, even when stdin is not one; None when there is no terminal.
        if sys.stdin.isatty():
            try:
                return input(question)
            except EOFError:
                return None
        try:
            with Path("/dev/tty").open("r+", encoding="utf-8") as terminal:
                terminal.write(question)
                terminal.flush()
                return terminal.readline()
        except OSError:
            return None


class Rules:
    """Runs FF001, FF002 and FF003 over the project.

    run() prints each violation and returns how many are left.
    """

    def __init__(self) -> None:
        self.files = [SourceFile(path) for path in self._python_files()]

    def run(self) -> int:
        violations = [found for file in self.files for found in file.violations()]
        reasons = Reasons()
        functions = [f for file in self.files for f in file.module_functions()]
        violations += [
            Violation(
                function.path,
                function.line,
                "FF003",
                f"{function.name} is outside any class and has no decorator;"
                " run `uv run format` in a terminal to give the reason",
            )
            for function in functions
            if function.key not in reasons.keys and not reasons.ask(function)
        ]
        reasons.stage()
        for violation in violations:
            print(violation, file=sys.stderr)
        if violations:
            plural = "" if len(violations) == 1 else "s"
            print(f"Found {len(violations)} error{plural}.", file=sys.stderr)
        return len(violations)

    @staticmethod
    def _python_files() -> Iterator[Path]:
        for directory in CHECKED_DIRS:
            for path in sorted((ROOT / directory).rglob("*.py")):
                relative = path.relative_to(ROOT).as_posix()
                if not relative.startswith(SKIPPED_DIRS):
                    yield path


def main() -> None:
    raise SystemExit(1 if Rules().run() else 0)


if __name__ == "__main__":
    main()
