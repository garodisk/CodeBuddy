"""Beautiful terminal UI components for Claude Code-style output."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Generator, Iterator

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


console = Console(force_terminal=True)


class TerminalUI:
    """Claude Code-style terminal UI with rich formatting."""

    def __init__(self):
        self.console = console

    # ─────────────────────────────────────────────────────────────────────
    # Spinners and Progress
    # ─────────────────────────────────────────────────────────────────────

    @contextmanager
    def spinner(self, message: str = "Thinking...") -> Generator[None, None, None]:
        """Show an animated spinner while processing."""
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[cyan]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            progress.add_task(message, total=None)
            yield

    @contextmanager
    def status(self, message: str) -> Generator[None, None, None]:
        """Show a status message with spinner."""
        with self.console.status(f"[cyan]{message}", spinner="dots"):
            yield

    def stream_text(self, token: str) -> None:
        """Stream a single token to the console (no newline)."""
        self.console.print(token, end="", markup=False)

    def stream_end(self) -> None:
        """End a streaming session with a newline."""
        self.console.print()

    def stream_tokens(self, tokens: Iterator[str], prefix: str = "") -> str:
        """Stream tokens from an iterator and return the full text."""
        if prefix:
            self.console.print(prefix, end="")

        full_text = ""
        for token in tokens:
            self.stream_text(token)
            full_text += token

        self.stream_end()
        return full_text

    # ─────────────────────────────────────────────────────────────────────
    # Tool Output Panels
    # ─────────────────────────────────────────────────────────────────────

    def tool_panel(self, tool_name: str, result: str, style: str = "dim") -> None:
        """Display tool execution result in a formatted panel."""
        # Determine icon based on tool
        icons = {
            "read_file": "[R]",
            "write_file": "[W]",
            "edit_file": "[E]",
            "list_files": "[L]",
            "run_cmd": "[>]",
            "grep": "[?]",
            "glob": "[*]",
        }
        icon = icons.get(tool_name, "[T]")

        panel = Panel(
            Text(result, overflow="fold"),
            title=f"{icon} {tool_name}",
            title_align="left",
            border_style=style,
            padding=(0, 1),
        )
        self.console.print(panel)

    def file_panel(self, filepath: str, content: str, language: str = "python") -> None:
        """Display file content with syntax highlighting."""
        syntax = Syntax(
            content,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        panel = Panel(
            syntax,
            title=f"[F] {filepath}",
            title_align="left",
            border_style="blue",
        )
        self.console.print(panel)

    # ─────────────────────────────────────────────────────────────────────
    # Diff Views
    # ─────────────────────────────────────────────────────────────────────

    def diff_panel(self, filepath: str, old_str: str, new_str: str) -> None:
        """Display a diff-style view of changes."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("change", style="dim")
        table.add_column("content")

        for line in old_str.splitlines():
            table.add_row("-", Text(line, style="red strike"))
        for line in new_str.splitlines():
            table.add_row("+", Text(line, style="green"))

        panel = Panel(
            table,
            title=f"[E] Edit: {filepath}",
            title_align="left",
            border_style="yellow",
        )
        self.console.print(panel)

    # ─────────────────────────────────────────────────────────────────────
    # Messages and Text
    # ─────────────────────────────────────────────────────────────────────

    def markdown(self, text: str) -> None:
        """Render markdown text."""
        self.console.print(Markdown(text))

    def code_block(self, code: str, language: str = "python") -> None:
        """Display a syntax-highlighted code block."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=False)
        self.console.print(syntax)

    def message(self, text: str, style: str = "") -> None:
        """Print a simple message."""
        self.console.print(text, style=style)

    def success(self, message: str) -> None:
        """Display a success message."""
        self.console.print(f"[green][+][/green] {message}")

    def error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[red][!][/red] {message}", style="red")

    def warning(self, message: str) -> None:
        """Display a warning message."""
        self.console.print(f"[yellow][*][/yellow] {message}", style="yellow")

    def info(self, message: str) -> None:
        """Display an info message."""
        self.console.print(f"[blue][i][/blue] {message}")

    # ─────────────────────────────────────────────────────────────────────
    # File Tree
    # ─────────────────────────────────────────────────────────────────────

    def file_tree(self, files: list[str], title: str = "Files") -> None:
        """Display files as a tree structure."""
        tree = Tree(Text(f"{title}", style="bold cyan"))

        # Group files by directory
        dirs: dict[str, list[str]] = {}
        for f in files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                dir_path = "/".join(parts[:-1])
                filename = parts[-1]
                if dir_path not in dirs:
                    dirs[dir_path] = []
                dirs[dir_path].append(filename)
            else:
                if "" not in dirs:
                    dirs[""] = []
                dirs[""].append(f)

        for dir_path, filenames in sorted(dirs.items()):
            if dir_path:
                branch = tree.add(Text(f"{dir_path}/", style="blue"))
                for fname in sorted(filenames):
                    branch.add(Text(fname, style="green"))
            else:
                for fname in sorted(filenames):
                    tree.add(Text(fname, style="green"))

        self.console.print(tree)

    # ─────────────────────────────────────────────────────────────────────
    # Todo List
    # ─────────────────────────────────────────────────────────────────────

    def todo_list(self, todos: list[dict]) -> None:
        """Display a todo list with status indicators."""
        status_icons = {
            "pending": "[ ]",
            "in_progress": "[~]",
            "completed": "[x]",
        }
        status_styles = {
            "pending": "dim",
            "in_progress": "yellow",
            "completed": "green",
        }

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("status", width=3)
        table.add_column("task")

        for todo in todos:
            status = todo.get("status", "pending")
            icon = status_icons.get(status, "☐")
            style = status_styles.get(status, "dim")
            content = todo.get("content", "")

            if status == "in_progress":
                content = todo.get("activeForm", content)

            table.add_row(
                Text(icon, style=style),
                Text(content, style=style if status != "in_progress" else "bold yellow"),
            )

        panel = Panel(table, title="Tasks", title_align="left", border_style="cyan")
        self.console.print(panel)

    # ─────────────────────────────────────────────────────────────────────
    # Status Line
    # ─────────────────────────────────────────────────────────────────────

    def status_line(self, agent: str = "", mode: str = "", tokens: int = 0) -> None:
        """Display a status line at the bottom."""
        parts = []
        if agent:
            parts.append(f"[cyan]Agent:[/cyan] {agent}")
        if mode:
            parts.append(f"[yellow]Mode:[/yellow] {mode}")
        if tokens:
            parts.append(f"[dim]Tokens:[/dim] {tokens:,}")

        if parts:
            self.console.print(" │ ".join(parts), style="dim")

    # ─────────────────────────────────────────────────────────────────────
    # Prompts
    # ─────────────────────────────────────────────────────────────────────

    def prompt(self, message: str = "> ") -> str:
        """Display a styled input prompt."""
        try:
            return self.console.input(f"[bold cyan]{message}[/bold cyan]")
        except EOFError:
            return ""

    def confirm(self, message: str) -> bool:
        """Ask for yes/no confirmation."""
        response = self.prompt(f"{message} [y/N] ")
        return response.lower() in ("y", "yes")

    # ─────────────────────────────────────────────────────────────────────
    # Headers and Dividers
    # ─────────────────────────────────────────────────────────────────────

    def header(self, text: str) -> None:
        """Display a header."""
        self.console.print()
        self.console.rule(f"[bold cyan]{text}[/bold cyan]", style="cyan")
        self.console.print()

    def divider(self) -> None:
        """Display a simple divider."""
        self.console.print("-" * 50, style="dim")

    def banner(self) -> None:
        """Display the app banner."""
        banner_text = """
+-----------------------------------------------------+
|                                                     |
|    CCCCC   OOOOO   DDDD    EEEEE   RRRR             |
|   C       O     O  D   D   E       R   R            |
|   C       O     O  D    D  EEEE    RRRR             |
|   C       O     O  D   D   E       R  R             |
|    CCCCC   OOOOO   DDDD    EEEEE   R   R            |
|                                                     |
|           Coder Buddy - AI Assistant                |
|                                                     |
+-----------------------------------------------------+
"""
        self.console.print(banner_text, style="cyan")

    def welcome(self) -> None:
        """Display welcome message."""
        self.banner()
        self.console.print()
        self.console.print("  [bold cyan]Welcome! I can help you build software projects.[/bold cyan]")
        self.console.print()
        self.console.print("  [bold]Getting Started:[/bold]")
        self.console.print("  [green]→[/green] First, choose whether to build a new project or edit an existing one")
        self.console.print("  [green]→[/green] Then, describe what you want to build")
        self.console.print("  [dim]    Example: 'a todo app' or 'a calculator with dark mode'[/dim]")
        self.console.print()
        self.console.print("  [bold]Tips:[/bold]")
        self.console.print("  [green]→[/green] Mention tech stack preferences (optional)")
        self.console.print("  [dim]    Example: 'using React' or 'with Python Flask'[/dim]")
        self.console.print()
        self.console.print("  [yellow]Commands:[/yellow] /new /help /status /exit")
        self.console.print()


# Global UI instance
ui = TerminalUI()
