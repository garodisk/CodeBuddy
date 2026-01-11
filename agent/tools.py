import pathlib
import re
import subprocess
from typing import Optional

from langchain_core.tools import tool


# Mutable project root - set dynamically based on project name
_project_root: pathlib.Path | None = None


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


def safe_path_for_project(path: str) -> pathlib.Path:
    """Resolve a path safely within the project root."""
    root = get_project_root()
    p = (root / path).resolve()
    if root.resolve() not in p.parents and root.resolve() != p.parent and root.resolve() != p:
        raise ValueError("Attempt to write outside project root")
    return p


@tool
def write_file(path: str, content: str) -> str:
    """Writes content to a file at the specified path within the project root."""
    p = safe_path_for_project(path)
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
def run_cmd(cmd: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
    """Runs a shell command in the specified directory and returns the result."""
    root = get_project_root()
    cwd_dir = safe_path_for_project(cwd) if cwd else root
    res = subprocess.run(
        cmd, shell=True, cwd=str(cwd_dir),
        capture_output=True, text=True, timeout=timeout
    )
    return {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
