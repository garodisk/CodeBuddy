# Coder-Buddy Architecture Analysis & Improvement Plan

## 1. Current Architecture Overview

### File Structure
```
Coder-buddy-claude/
├── main.py                 # Entry point - CLI interface
├── agent/
│   ├── __init__.py        # Package init (empty)
│   ├── graph.py           # LangGraph state machine (104 lines)
│   ├── states.py          # Pydantic models for state (64 lines)
│   ├── tools.py           # File I/O tools (61 lines)
│   └── prompts.py         # System prompts
├── pyproject.toml         # UV-based Python 3.12+ project
└── .env                   # API keys (OpenAI, Anthropic, Groq, etc.)
```

### Agent Flow (Three-Stage Pipeline)
```
User Prompt
    ↓
┌─────────────────────────────────────────────┐
│ PLANNER AGENT                               │
│ Input: user_prompt                          │
│ Output: Plan (name, description, techstack, │
│         features, files)                    │
│ Uses: GPT-5.2 with structured output        │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ ARCHITECT AGENT                                  │
│ Input: Plan                                      │
│ Output: TaskPlan (list of ImplementationTask:   │
│         filepath + task_description)            │
│ Uses: GPT-5.2 with structured output            │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ CODER AGENT (loops until all tasks done)        │
│ Input: TaskPlan + step index                    │
│ Output: Written files                           │
│ Uses: ReAct agent with tools                    │
└─────────────────────────────────────────────────┘
    ↓
DONE (files created in generated_project/)
```

### Current Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| `write_file(path, content)` | Create/overwrite files | Full file write only |
| `read_file(path)` | Read file contents | Returns empty string if missing |
| `list_files(directory)` | Recursive file listing | Uses glob `**/*` |
| `get_current_directory()` | Get PROJECT_ROOT | Static value |
| `run_cmd(cmd, cwd, timeout)` | Shell execution | **Defined but NOT exposed to agent** |

---

## 2. Gaps vs Real Claude Code

### Critical Missing Features

| Feature | Claude Code | Coder-Buddy | Impact |
|---------|-------------|-------------|--------|
| **Beautiful terminal UI** | Rich formatting, colors, spinners | Plain text output | Poor user experience |
| **Interactive conversation** | Continuous back-and-forth | One-shot generation | Cannot iterate with user |
| **Streaming output** | Real-time token display | Wait for full response | Feels slow/unresponsive |
| **Edit tool** | Diff-based edits | Full file rewrites | Inefficient, loses context |
| **Glob/Grep tools** | Fast pattern matching | Only `list_files` | Poor codebase exploration |
| **Human-in-the-loop** | `AskUserQuestion` tool | None | Cannot clarify requirements |
| **Plan mode** | Research before coding | Always executes immediately | May miss requirements |
| **Task management** | TodoWrite for tracking | None | No progress visibility |
| **Git operations** | Commits, PRs, branches | None | No version control |

---

## 3. Prioritized Improvement Plan

### Phase 1: Beautiful Terminal UI (User Experience)
**Goal**: Rich, Claude Code-style terminal interface

1. **Add Rich library for terminal formatting**
   - Dependency: `rich` package
   - Colored output, markdown rendering
   - Syntax highlighting for code blocks

2. **Add status spinners and progress indicators**
   - Show "Thinking..." with animated spinner
   - Display tool execution status
   - Progress bars for multi-step tasks

3. **Implement streaming output**
   - Display LLM tokens as they arrive
   - Real-time response rendering
   - Typing effect for natural feel

4. **Add formatted tool output**
   - Box/panel formatting for tool results
   - File diffs with syntax highlighting
   - Collapsible sections for large outputs

5. **Create status line**
   - Show current agent/mode
   - Display token usage
   - Show active file/directory

**Terminal UI Examples:**
```
┌─ Claude Code ─────────────────────────────────┐
│ ● Reading file: src/main.py                   │
└───────────────────────────────────────────────┘

╭─ Edit ──────────────────────────────────────────╮
│ src/utils.py                                    │
│ ─────────────────────────────────────────────── │
│ - def old_function():                           │
│ + def new_function():                           │
╰─────────────────────────────────────────────────╯

⠋ Thinking...
```

### Phase 2: Core Interactive Loop (Foundation)
**Goal**: Transform from one-shot to interactive assistant

6. **Add conversation REPL loop**
   - File: `main.py`
   - Create input loop with Rich prompt
   - Maintain conversation state between turns
   - Support `/exit`, `/clear`, `/help` commands

7. **Add AskUserQuestion tool**
   - File: `agent/tools.py`
   - Allow agent to pause and request user input
   - Beautiful formatted question prompts

8. **Expose run_cmd to agent**
   - File: `agent/graph.py`
   - Add `run_cmd` to `coder_tools` list
   - Show command output in formatted panels

### Phase 3: Better Code Manipulation
**Goal**: Efficient editing and exploration

9. **Add Edit tool (diff-based)**
    - File: `agent/tools.py`
    - Parameters: `file_path`, `old_string`, `new_string`
    - Show beautiful diffs in terminal

10. **Add Glob tool**
    - Fast pattern matching for file discovery
    - Display results as tree structure

11. **Add Grep tool**
    - Search file contents with regex
    - Highlighted matches in context

### Phase 4: Task Management & Planning
**Goal**: Visibility and planning capability

12. **Add TodoWrite tool**
    - Track tasks with status indicators
    - Display as checklist: ☐ ☑ ◐
    - Real-time progress updates

13. **Add Plan mode**
    - Explore codebase before changes
    - Display plan in formatted panel
    - Get user approval with Y/N prompt

### Phase 5: Enhanced Capabilities
**Goal**: Full-featured assistant

14. **Add Git operations**
    - Formatted diff display
    - Commit message previews
    - PR creation with status

15. **Switch to Claude API**
    - Use Anthropic SDK
    - Access Claude Opus 4.5

---

## 4. Terminal UI Components to Build

### Core UI Module (`agent/ui.py`)

```python
# Components needed:
class TerminalUI:
    def spinner(message: str)      # Animated thinking indicator
    def stream_text(tokens)        # Real-time text display
    def tool_panel(name, result)   # Formatted tool output
    def diff_view(old, new)        # Side-by-side or unified diff
    def file_tree(files)           # Tree structure display
    def todo_list(todos)           # Checkbox list
    def prompt()                   # Styled input prompt
    def error(message)             # Red error box
    def success(message)           # Green success box
    def code_block(code, lang)     # Syntax highlighted code
    def markdown(text)             # Rendered markdown
```

### Recommended Libraries
- `rich` - Primary formatting library
- `prompt_toolkit` - Advanced input handling
- `pygments` - Syntax highlighting (used by rich)

---

## 5. Verification Plan

After each phase, verify:

1. **Phase 1**: Run app, see colored output, spinners, streaming text
2. **Phase 2**: Have multi-turn conversation, agent asks you questions
3. **Phase 3**: Ask agent to find and edit a function, see beautiful diff
4. **Phase 4**: See todo checklist update in real-time
5. **Phase 5**: Commit changes, see formatted git output

---

## 6. Critical Files to Modify/Create

| File | Changes |
|------|---------|
| `agent/ui.py` | **NEW** - Terminal UI components |
| `main.py` | Add REPL loop, integrate UI |
| `agent/graph.py` | Add streaming, new tools |
| `agent/tools.py` | Add Edit, Glob, Grep, Todo, AskUser |
| `agent/states.py` | Add TodoState, ConversationState |
| `pyproject.toml` | Add `rich`, `prompt_toolkit` dependencies |

---

## 7. Quick Wins (Immediate Impact)

1. **Add `rich` and show colored output** - 30 min
2. **Expose `run_cmd` to agent** - 1 line change
3. **Add spinner during LLM calls** - Simple wrapper
4. **Format tool results in panels** - Use `rich.panel`

---

## Recommendation

**Start with Phase 1 (Terminal UI)**: Beautiful output transforms the user experience immediately. Even the current one-shot functionality will feel more polished with proper formatting, spinners, and syntax highlighting.

The terminal UI creates the foundation for all other improvements - streaming, tool output display, and interactive prompts all depend on having a proper UI layer.
