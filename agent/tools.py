import pathlib
import re
import subprocess
from typing import Optional

from langchain_core.tools import tool


# Mutable project root - set dynamically based on project name
_project_root: pathlib.Path | None = None

# Permission mode for tools - set from main.py
_permission_mode: str = "strict"  # "strict" or "permissive"

# Dangerous command patterns
DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"sudo\s+",
    r"chmod\s+777",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"dd\s+if=",
    r"mkfs\.",
    r":(){ :|:& };:",  # fork bomb
    r">\s*/dev/sd",
    r"mv.*\s+/dev/null",
    # Additional patterns for git and other dangerous commands
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-[a-z]*f",   # matches -f, -fd, -fdx, etc.
    r"chmod\s+-R",
    r"rm\s+-r\b",                 # rm -r without -f (still dangerous)
    r"(?i)powershell.*invoke-expression",
    r"(?i)powershell.*iex\s",
]


def get_project_root() -> pathlib.Path:
    """Get the current project root, raising if not set."""
    if _project_root is None:
        raise RuntimeError("Project root not initialized. Call set_project_root() first.")
    return _project_root


def set_project_root(name: str) -> pathlib.Path:
    """Set the project root based on project name. Returns the path."""
    global _project_root

    # Sanitize the name for filesystem
    safe_name = re.sub(r'[^\w\-]', '-', name.lower().strip())
    safe_name = re.sub(r'-+', '-', safe_name).strip('-')

    if not safe_name:
        safe_name = "project"

    _project_root = pathlib.Path.cwd() / safe_name
    _project_root.mkdir(parents=True, exist_ok=True)

    return _project_root


def set_permission_mode(mode: str) -> None:
    """Set the permission mode for dangerous operations."""
    global _permission_mode
    if mode not in ("strict", "permissive"):
        raise ValueError(f"Invalid permission mode: {mode}")
    _permission_mode = mode


def is_dangerous_command(cmd: str) -> bool:
    """Check if a command matches any dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return True
    return False


def safe_path_for_project(path: str) -> pathlib.Path:
    """Resolve a path safely within the project root."""
    root = get_project_root().resolve()
    p = (root / path).resolve()
    # Strict check: p must be root itself or have root as ancestor
    if root != p and root not in p.parents:
        raise ValueError("Attempt to access outside project root")
    return p


@tool
def write_file(path: str, content: str, confirm_overwrite: bool = True) -> str:
    """
    Writes content to a file at the specified path within the project root.

    Args:
        path: File path within the project root
        content: Content to write
        confirm_overwrite: If True and in strict mode, ask before overwriting existing files

    Returns:
        Success message
    """
    from agent.ui import ui

    p = safe_path_for_project(path)

    # Check if path is a directory
    if p.exists() and p.is_dir():
        return f"ERROR: {path} is a directory, cannot write"

    # Check if file exists and ask for confirmation in strict mode
    if _permission_mode == "strict" and confirm_overwrite and p.exists():
        ui.warning(f"File {path} already exists")
        if not ui.confirm("Overwrite?"):
            return f"ERROR: Write to {path} cancelled by user"

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return f"WROTE:{p}"


@tool
def read_file(path: str) -> str:
    """Reads content from a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


@tool
def edit_file(path: str, old_str: str, new_str: str) -> str:
    """
    Performs precise string replacement in a file.

    Args:
        path: File path within the project root
        old_str: Exact string to find and replace (must appear exactly once)
        new_str: Replacement string

    Returns:
        Success message or error

    Raises:
        ValueError: If old_str appears 0 or >1 times in the file
    """
    from agent.ui import ui

    p = safe_path_for_project(path)
    if not p.exists():
        return f"ERROR: File {path} does not exist"

    # Read current content
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # Count occurrences
    count = content.count(old_str)

    if count == 0:
        return f"ERROR: String not found in {path}"
    elif count > 1:
        return f"ERROR: String appears {count} times in {path} (must be unique)"

    # Perform replacement
    new_content = content.replace(old_str, new_str, 1)

    # Show diff
    ui.diff_panel(path, old_str, new_str)

    # Write back
    with open(p, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"EDITED:{p}"


@tool
def get_current_directory() -> str:
    """Returns the current working directory (project root)."""
    return str(get_project_root())


@tool
def list_files(directory: str = ".") -> str:
    """Lists all files in the specified directory within the project root."""
    root = get_project_root()
    p = safe_path_for_project(directory)
    if not p.is_dir():
        return f"ERROR: {p} is not a directory"
    files = [str(f.relative_to(root)) for f in p.glob("**/*") if f.is_file()]
    return "\n".join(files) if files else "No files found."


@tool
def glob_files(pattern: str, max_results: int = 100) -> str:
    """
    Find files matching a glob pattern within the project root.

    Args:
        pattern: Glob pattern (e.g., "*.py", "src/**/*.js", "**/*.md")
        max_results: Maximum number of results to return

    Returns:
        Newline-separated list of matching file paths
    """
    root = get_project_root()

    try:
        # Use pathlib glob from root
        matches = list(root.glob(pattern))

        # Filter to files only and limit results
        files = [str(f.relative_to(root)) for f in matches if f.is_file()][:max_results]

        if not files:
            return f"No files found matching pattern: {pattern}"

        result = "\n".join(files)
        if len(matches) > max_results:
            result += f"\n... ({len(matches) - max_results} more files)"

        return result

    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def grep(pattern: str, path: str = ".", max_results: int = 50, ignore_case: bool = False) -> str:
    """
    Search file contents using regex patterns within the project root.

    Args:
        pattern: Regular expression pattern to search for
        path: File or directory path to search (default: project root)
        max_results: Maximum number of matching lines to return
        ignore_case: Case-insensitive search if True

    Returns:
        Formatted list of matches with file:line_number:content
    """
    root = get_project_root()
    search_path = safe_path_for_project(path)

    try:
        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"ERROR: Invalid regex pattern: {e}"

    matches = []
    files_to_search = []

    # Determine files to search
    if search_path.is_file():
        files_to_search = [search_path]
    elif search_path.is_dir():
        files_to_search = [f for f in search_path.rglob("*") if f.is_file()]
    else:
        return f"ERROR: Path {path} does not exist"

    # Search files
    for file_path in files_to_search:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(root)
                        matches.append(f"{rel_path}:{line_num}:{line.rstrip()}")

                        if len(matches) >= max_results:
                            break
        except Exception:
            # Skip files that can't be read
            continue

        if len(matches) >= max_results:
            break

    if not matches:
        return f"No matches found for pattern: {pattern}"

    result = "\n".join(matches)
    if len(matches) >= max_results:
        result += f"\n... (limit of {max_results} results reached)"

    return result


@tool
def run_cmd(cmd: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
    """Runs a shell command in the specified directory and returns the result."""
    from agent.ui import ui

    # Check for dangerous commands in strict mode
    if _permission_mode == "strict" and is_dangerous_command(cmd):
        ui.warning(f"Dangerous command detected: {cmd}")
        if not ui.confirm("Allow execution?"):
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "ERROR: Command blocked by user"
            }

    root = get_project_root()
    cwd_dir = safe_path_for_project(cwd) if cwd else root
    res = subprocess.run(
        cmd, shell=True, cwd=str(cwd_dir),
        capture_output=True, text=True, timeout=timeout
    )
    return {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
