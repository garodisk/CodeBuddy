# Coder Buddy

A Claude Code-style AI coding assistant built with LangGraph. Transforms natural language prompts into complete, working projects through a multi-agent pipeline.

```
+-----------------------------------------------------+
|    CCCCC   OOOOO   DDDD    EEEEE   RRRR             |
|   C       O     O  D   D   E       R   R            |
|   C       O     O  D    D  EEEE    RRRR             |
|   C       O     O  D   D   E       R  R             |
|    CCCCC   OOOOO   DDDD    EEEEE   R   R            |
|                                                     |
|           Coder Buddy - AI Assistant                |
+-----------------------------------------------------+
```

## Features

- **Multi-Agent Architecture** - Three specialized agents (Planner, Architect, Coder) work together
- **Beautiful Terminal UI** - Rich formatting, spinners, progress indicators, and syntax highlighting
- **Streaming Output** - Real-time token streaming as the AI thinks
- **Dynamic Project Folders** - Projects created in named directories (e.g., `todo-app/`, `snake-game/`)
- **Interactive REPL** - Continuous conversation with slash commands
- **Tool Integration** - File operations, shell commands, and more
- **Sandboxed Execution** - All file operations confined to project directory

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/coder-buddy-claude.git
cd coder-buddy-claude

# Install dependencies
uv sync

# Create .env file with your API key
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Usage

### Interactive Mode

```bash
uv run python main.py
```

This starts the REPL where you can type project requests:

```
> Create a snake game in Python with pygame
> Build a REST API with FastAPI and SQLite
> Make a React todo app with local storage
```

### Single Prompt Mode

```bash
uv run python main.py --prompt "Create a calculator web app"
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/clear` | Clear the screen |
| `/exit` | Exit the application |

---

## Architecture

### LangGraph State Machine

Coder Buddy uses a **three-agent pipeline** orchestrated by LangGraph:

```
                              +------------------+
                              |   User Prompt    |
                              +--------+---------+
                                       |
                                       v
                    +------------------+------------------+
                    |                                     |
                    |          PLANNER AGENT              |
                    |                                     |
                    |  - Analyzes user request            |
                    |  - Determines project name          |
                    |  - Identifies tech stack            |
                    |  - Lists features & files           |
                    |                                     |
                    |  Output: Plan                       |
                    |    {name, description, techstack,   |
                    |     features[], files[]}            |
                    |                                     |
                    +------------------+------------------+
                                       |
                                       v
                    +------------------+------------------+
                    |                                     |
                    |         ARCHITECT AGENT             |
                    |                                     |
                    |  - Breaks plan into tasks           |
                    |  - Orders by dependencies           |
                    |  - Specifies implementations        |
                    |  - Defines function signatures      |
                    |                                     |
                    |  Output: TaskPlan                   |
                    |    {implementation_steps[           |
                    |       {filepath, task_description}  |
                    |     ]}                              |
                    |                                     |
                    +------------------+------------------+
                                       |
                                       v
                    +------------------+------------------+
                    |                                     |
                    |           CODER AGENT               |
                    |                                     |
                    |  - Implements each task             |
                    |  - Uses ReAct agent with tools      |
                    |  - Reads related files first        |
                    |  - Writes complete file content     |
                    |  - Maintains context across steps   |
                    |                                     |
                    |  Tools: read_file, write_file,      |
                    |         list_files, run_cmd,        |
                    |         get_current_directory       |
                    |                                     |
                    +------------------+------------------+
                                       |
                          +------------+------------+
                          |                         |
                          v                         |
                   +------+------+                  |
                   | More tasks? |------ YES -------+
                   +------+------+     (loop back)
                          |
                          | NO
                          v
                    +-----+-----+
                    |   DONE    |
                    +-----------+
```

### Detailed Graph Flow

```
+===========================================================================+
|                           LANGGRAPH EXECUTION                             |
+===========================================================================+
|                                                                           |
|  START                                                                    |
|    |                                                                      |
|    v                                                                      |
|  +-----------------------------------------------------------------------+|
|  | PLANNER NODE                                                          ||
|  |-----------------------------------------------------------------------|+
|  |                                                                       ||
|  |  Input:  GraphState { user_prompt: "Create a todo app" }              ||
|  |                                                                       ||
|  |  Process:                                                             ||
|  |    1. llm.with_structured_output(Plan).invoke(planner_prompt)         ||
|  |    2. set_project_root(plan.name)  -->  Creates ./todo-app/           ||
|  |    3. Display plan to user with UI                                    ||
|  |                                                                       ||
|  |  Output: GraphState += { plan: Plan(...) }                            ||
|  |                                                                       ||
|  +-----------------------------------------------------------------------+|
|    |                                                                      |
|    | (sequential edge)                                                    |
|    v                                                                      |
|  +-----------------------------------------------------------------------+|
|  | ARCHITECT NODE                                                        ||
|  |-----------------------------------------------------------------------|+
|  |                                                                       ||
|  |  Input:  GraphState { user_prompt, plan }                             ||
|  |                                                                       ||
|  |  Process:                                                             ||
|  |    1. llm.with_structured_output(TaskPlan).invoke(architect_prompt)   ||
|  |    2. Display task list with UI                                       ||
|  |                                                                       ||
|  |  Output: GraphState += { task_plan: TaskPlan(...) }                   ||
|  |                                                                       ||
|  +-----------------------------------------------------------------------+|
|    |                                                                      |
|    | (sequential edge)                                                    |
|    v                                                                      |
|  +-----------------------------------------------------------------------+|
|  | CODER NODE                                                     <----+ ||
|  |--------------------------------------------------------------------| | ||
|  |                                                                    | | ||
|  |  Input:  GraphState { user_prompt, plan, task_plan, coder_state }  | | ||
|  |                                                                    | | ||
|  |  Process:                                                          | | ||
|  |    1. Initialize coder_state if None (step_idx = 0)                | | ||
|  |    2. Check if step_idx >= len(steps) --> return DONE              | | ||
|  |    3. Get current task from implementation_steps[step_idx]         | | ||
|  |    4. Build context message with task description                  | | ||
|  |    5. react_agent.stream() --> Stream thinking + tool calls        | | ||
|  |    6. Increment step_idx                                           | | ||
|  |                                                                    | | ||
|  |  Output: GraphState += { coder_state, messages, status? }          | | ||
|  |                                                                    | | ||
|  +-----------------------------------------------------------------------+|
|    |                                                                  ^   |
|    | (conditional edge)                                               |   |
|    v                                                                  |   |
|  +-------------------+                                                |   |
|  | status == "DONE"? |                                                |   |
|  +-------------------+                                                |   |
|    |           |                                                      |   |
|    | YES       | NO                                                   |   |
|    v           +------------------------------------------------------+   |
|  +-----+                        (loop back to CODER)                      |
|  | END |                                                                  |
|  +-----+                                                                  |
|                                                                           |
+===========================================================================+
```

### Graph Definition (Code)

```python
from langgraph.graph import StateGraph
from langgraph.constants import END

# Create the graph with state schema
graph = StateGraph(GraphState)

# Add nodes (each is a function that transforms state)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

# Add sequential edges
graph.add_edge("planner", "architect")    # planner --> architect
graph.add_edge("architect", "coder")      # architect --> coder

# Add conditional edge (loop or exit)
graph.add_conditional_edges(
    "coder",                                           # from node
    lambda s: "END" if s.get("status") == "DONE" else "coder",  # condition
    {"END": END, "coder": "coder"}                     # routing map
)

# Set entry point
graph.set_entry_point("planner")

# Compile to executable
agent = graph.compile()
```

---

## State Schema

### GraphState (TypedDict)

The central state object passed through all nodes:

```
GraphState
+----------------------------------------------------------+
|                                                          |
|  user_prompt: str          # Original user request       |
|                            # Example: "Create a todo app"|
|                                                          |
|  plan: Plan                # Output from Planner         |
|    +-- name: str           # "Todo App"                  |
|    +-- description: str    # "A simple todo application" |
|    +-- techstack: str      # "React, TypeScript"         |
|    +-- features: list[str] # ["Add todos", "Delete"]     |
|    +-- files: list[File]   # Files to create             |
|          +-- path: str     # "src/App.tsx"               |
|          +-- purpose: str  # "Main component"            |
|                                                          |
|  task_plan: TaskPlan       # Output from Architect       |
|    +-- implementation_steps: list[ImplementationTask]    |
|          +-- filepath: str          # "src/App.tsx"      |
|          +-- task_description: str  # "Create App..."    |
|                                                          |
|  coder_state: CoderState   # Tracks Coder progress       |
|    +-- task_plan: TaskPlan # Reference to task plan      |
|    +-- current_step_idx: int  # 0, 1, 2, ...             |
|                                                          |
|  messages: list[Message]   # Full conversation history   |
|                            # Preserved across all steps  |
|                                                          |
|  status: str               # "DONE" when complete        |
|                                                          |
+----------------------------------------------------------+
```

### Message Flow

```
Step 1:                          Step 2:                         Step 3:
+-------------------------+      +-------------------------+     +-------------------------+
| SystemMessage           |      | SystemMessage           |     | SystemMessage           |
| HumanMessage (request)  |      | HumanMessage (request)  |     | HumanMessage (request)  |
| HumanMessage (task 1)   |      | HumanMessage (task 1)   |     | HumanMessage (task 1)   |
| AIMessage (thinking)    |      | AIMessage (thinking)    |     | AIMessage (thinking)    |
| ToolMessage (result)    |      | ToolMessage (result)    |     | ToolMessage (result)    |
| AIMessage (done)        |      | AIMessage (done)        |     | AIMessage (done)        |
+-------------------------+      | HumanMessage (task 2)   |     | HumanMessage (task 2)   |
                                 | AIMessage (thinking)    |     | AIMessage (thinking)    |
                                 | ToolMessage (result)    |     | ToolMessage (result)    |
                                 | AIMessage (done)        |     | AIMessage (done)        |
                                 +-------------------------+     | HumanMessage (task 3)   |
                                                                 | ...                     |
                                                                 +-------------------------+

Messages accumulate across steps, giving the Coder full context.
```

---

## Project Structure

```
coder-buddy-claude/
|
|-- main.py                 # Entry point
|   |-- main()              # Parse args, start REPL
|   |-- repl()              # Interactive loop
|   |-- run_agent()         # Invoke the graph
|   +-- handle_command()    # Process /help, /exit, etc.
|
|-- pyproject.toml          # Project config (uv)
|-- .env                    # API keys (OPENAI_API_KEY)
|
+-- agent/
|   |
|   |-- __init__.py
|   |
|   |-- graph.py            # LangGraph definition
|   |   |-- llm             # ChatOpenAI instance
|   |   |-- react_agent     # ReAct agent with tools
|   |   |-- planner_agent() # Node: creates Plan
|   |   |-- architect_agent()  # Node: creates TaskPlan
|   |   |-- coder_agent()   # Node: implements tasks
|   |   +-- agent           # Compiled graph
|   |
|   |-- states.py           # Pydantic models
|   |   |-- File            # {path, purpose}
|   |   |-- Plan            # {name, desc, tech, features, files}
|   |   |-- ImplementationTask  # {filepath, task_description}
|   |   |-- TaskPlan        # {implementation_steps[]}
|   |   |-- CoderState      # {task_plan, current_step_idx}
|   |   +-- GraphState      # TypedDict for graph state
|   |
|   |-- tools.py            # LangChain tools
|   |   |-- set_project_root()  # Set dynamic project folder
|   |   |-- get_project_root()  # Get current project path
|   |   |-- safe_path_for_project()  # Sandbox validation
|   |   |-- @tool read_file()
|   |   |-- @tool write_file()
|   |   |-- @tool list_files()
|   |   |-- @tool get_current_directory()
|   |   +-- @tool run_cmd()
|   |
|   |-- prompts.py          # System prompts
|   |   |-- planner_prompt()
|   |   |-- architect_prompt()
|   |   +-- coder_system_prompt()
|   |
|   +-- ui.py               # Terminal UI (Rich)
|       |-- TerminalUI class
|       |-- spinner()       # Animated spinner
|       |-- stream_text()   # Real-time output
|       |-- tool_panel()    # Formatted tool results
|       |-- file_tree()     # Tree view of files
|       |-- todo_list()     # Task checklist
|       |-- success/error/warning/info()
|       +-- banner/welcome()
|
+-- docs/
    +-- PLAN.md             # Future improvements
```

---

## How It Works (Step by Step)

### Example: "Create a calculator web app"

#### Step 1: User Input

```
> Create a calculator web app
```

The REPL captures this and calls:
```python
agent.invoke({"user_prompt": "Create a calculator web app"})
```

#### Step 2: Planner Agent

```
[*] Planning project...
```

The Planner calls GPT-4o with structured output:

```python
llm.with_structured_output(Plan).invoke("""
You are the PLANNER agent. Convert the user prompt into a COMPLETE engineering project plan.

User request:
Create a calculator web app
""")
```

**Output:**
```json
{
  "name": "Calculator Web App",
  "description": "A simple calculator with basic arithmetic operations",
  "techstack": "HTML, CSS, JavaScript",
  "features": ["Addition", "Subtraction", "Multiplication", "Division", "Clear"],
  "files": [
    {"path": "index.html", "purpose": "Main HTML structure"},
    {"path": "styles.css", "purpose": "Calculator styling"},
    {"path": "script.js", "purpose": "Calculator logic"}
  ]
}
```

Creates directory: `./calculator-web-app/`

#### Step 3: Architect Agent

```
[*] Designing architecture...
```

The Architect breaks down the plan:

```json
{
  "implementation_steps": [
    {
      "filepath": "index.html",
      "task_description": "Create HTML with calculator display div (id='display'), number buttons 0-9 (class='btn-num'), operator buttons +,-,*,/ (class='btn-op'), equals button (id='equals'), clear button (id='clear'). Include links to styles.css and script.js."
    },
    {
      "filepath": "styles.css",
      "task_description": "Style calculator with grid layout. Display should be right-aligned. Buttons should be 60px squares with hover effects. Use #333 background, white text."
    },
    {
      "filepath": "script.js",
      "task_description": "Implement calculator logic. Variables: currentValue, previousValue, operator. Functions: appendNumber(num), setOperator(op), calculate(), clearDisplay(). Add event listeners to all buttons."
    }
  ]
}
```

**Display:**
```
+-- Tasks -------------------------------------------------+
| [ ] Create HTML with calculator display div...          |
| [ ] Style calculator with grid layout...                |
| [ ] Implement calculator logic...                       |
+---------------------------------------------------------+
```

#### Step 4: Coder Agent (Loop)

**Iteration 1: index.html**

```
--------------------------------------------------
Step 1/3: index.html
Thinking...
[i] Writing: index.html
[+] Completed: index.html
```

The Coder streams its response:
```
I'll create the HTML structure for the calculator...
```

Then calls `write_file("index.html", "<!DOCTYPE html>...")`.

**Iteration 2: styles.css**

```
--------------------------------------------------
Step 2/3: styles.css
Thinking...
[i] Reading: index.html      <-- Reads to check class names
[i] Writing: styles.css
[+] Completed: styles.css
```

**Iteration 3: script.js**

```
--------------------------------------------------
Step 3/3: script.js
Thinking...
[i] Reading: index.html      <-- Reads to check IDs
[i] Writing: script.js
[+] Completed: script.js
```

#### Step 5: Complete

```
======================== Complete ========================

[+] Project generated successfully!

Generated Files
+-- index.html
+-- styles.css
+-- script.js
```

The project is now at `./calculator-web-app/`:

```
calculator-web-app/
|-- index.html
|-- styles.css
+-- script.js
```

---

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `read_file` | `(path: str) -> str` | Read file contents |
| `write_file` | `(path: str, content: str) -> str` | Write file |
| `list_files` | `(directory: str = ".") -> str` | List files recursively |
| `get_current_directory` | `() -> str` | Get project root path |
| `run_cmd` | `(cmd: str, cwd: str?, timeout: int?) -> dict` | Run shell command |

### Sandbox Protection

All tools validate paths:

```python
def safe_path_for_project(path: str) -> pathlib.Path:
    root = get_project_root()
    p = (root / path).resolve()
    if root.resolve() not in p.parents and root.resolve() != p:
        raise ValueError("Attempt to write outside project root")
    return p
```

This prevents:
- `../../etc/passwd` - Path traversal
- `/absolute/path` - Absolute paths outside project
- `../sibling` - Accessing sibling directories

---

## Terminal UI

Built with [Rich](https://rich.readthedocs.io/):

| Component | Method | Description |
|-----------|--------|-------------|
| Spinner | `ui.spinner("msg")` | Animated dots during LLM calls |
| Streaming | `ui.stream_text(token)` | Print tokens in real-time |
| Panels | `ui.tool_panel(name, result)` | Boxed tool output |
| Trees | `ui.file_tree(files)` | Directory structure |
| Messages | `ui.success/error/warning/info(msg)` | Colored status messages |
| Progress | Step X/Y display | Track implementation progress |

---

## Configuration

### Environment Variables (.env)

```env
OPENAI_API_KEY=sk-...
```

### Model Selection (graph.py)

```python
llm = ChatOpenAI(
    model="gpt-4o",           # Model name
    temperature=0,            # Deterministic output
    streaming=True,           # Enable streaming
)
```

Options:
- `gpt-4o` - Best quality (recommended)
- `gpt-4-turbo` - Faster, slightly lower quality
- `gpt-3.5-turbo` - Fastest, lowest cost

---

## Roadmap

See [docs/PLAN.md](docs/PLAN.md) for details:

### Phase 2: Better Code Manipulation
- [ ] Edit tool (diff-based)
- [ ] Glob tool (file patterns)
- [ ] Grep tool (content search)

### Phase 3: Task Management
- [ ] TodoWrite tool
- [ ] Plan mode

### Phase 4: Enhanced Capabilities
- [ ] Git operations
- [ ] Web search
- [ ] Switch to Claude API

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

## License

MIT

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Claude Code](https://claude.ai/code) - Inspiration
