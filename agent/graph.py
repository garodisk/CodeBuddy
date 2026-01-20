from __future__ import annotations

from dotenv import load_dotenv
from langchain_core.globals import set_debug, set_verbose
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent

from agent.prompts import architect_prompt, coder_system_prompt, planner_prompt
from agent.states import CoderState, GraphState, Plan, TaskPlan, ClarificationRequest
from agent.tools import (
    get_current_directory, list_files, read_file, write_file, run_cmd,
    set_project_root, edit_file, glob_files, grep, _project_root
)
import pathlib
from agent.ui import ui


_ = load_dotenv()
set_debug(False)  # Disable debug for cleaner output
set_verbose(False)

llm = ChatOpenAI(
    model="gpt-4o",  # or gpt-5.1 / gpt-5
    temperature=0,
    streaming=True,  # Enable streaming
)

# Include all tools for the coder agent
coder_tools = [
    read_file, write_file, edit_file, list_files,
    glob_files, grep, get_current_directory, run_cmd
]
react_agent = create_react_agent(llm, coder_tools)


def discover_project(state: GraphState) -> GraphState:
    """
    Discover project structure and read key files BEFORE planning.
    Only runs in edit mode.
    """
    mode = state.get("mode", "build")

    if mode != "edit":
        # Skip discovery in build mode
        return {"project_context": None}

    project_root = state.get("project_root", ".")

    ui.header("Discovering Project Structure")
    ui.message("")

    # Set up the project root for tools
    import agent.tools
    agent.tools._project_root = pathlib.Path(project_root)

    context_parts = []

    # 1. Get directory tree
    ui.info("Reading project structure...")
    try:
        import os
        tree_lines = []
        for root, dirs, files in os.walk(project_root):
            # Skip common non-essential directories
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '.git', '__pycache__', '.venv', 'venv',
                'dist', 'build', '.next', '.cache', 'coverage'
            ]]

            level = root.replace(project_root, '').count(os.sep)
            indent = '  ' * level
            folder_name = os.path.basename(root) or project_root
            tree_lines.append(f"{indent}{folder_name}/")

            sub_indent = '  ' * (level + 1)
            for file in files[:20]:  # Limit files per directory
                tree_lines.append(f"{sub_indent}{file}")

            if len(tree_lines) > 100:  # Limit total tree size
                tree_lines.append("  ... (truncated)")
                break

        tree_str = '\n'.join(tree_lines[:100])
        context_parts.append(f"PROJECT STRUCTURE:\n{tree_str}")
        ui.message(f"[dim]Found {len(tree_lines)} items[/dim]")
    except Exception as e:
        ui.warning(f"Could not read project structure: {e}")

    # 2. Read README if exists
    ui.info("Looking for README...")
    readme_files = ['README.md', 'README.txt', 'README', 'readme.md']
    for readme in readme_files:
        readme_path = pathlib.Path(project_root) / readme
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding='utf-8')[:3000]
                context_parts.append(f"README ({readme}):\n{content}")
                ui.success(f"Found {readme}")
                break
            except Exception:
                pass

    # 3. Read package.json or requirements.txt for dependencies
    ui.info("Looking for dependency files...")
    dep_files = [
        ('package.json', 'PACKAGE.JSON (Node.js dependencies)'),
        ('requirements.txt', 'REQUIREMENTS.TXT (Python dependencies)'),
        ('pyproject.toml', 'PYPROJECT.TOML (Python project config)'),
        ('Cargo.toml', 'CARGO.TOML (Rust dependencies)'),
        ('go.mod', 'GO.MOD (Go dependencies)'),
    ]
    for dep_file, label in dep_files:
        dep_path = pathlib.Path(project_root) / dep_file
        if dep_path.exists():
            try:
                content = dep_path.read_text(encoding='utf-8')[:2000]
                context_parts.append(f"{label}:\n{content}")
                ui.success(f"Found {dep_file}")
            except Exception:
                pass

    # 4. Read main entry files
    ui.info("Looking for main code files...")
    main_files = [
        'index.js', 'index.ts', 'main.py', 'app.py', 'server.js', 'server.py',
        'main.js', 'main.ts', 'App.js', 'App.tsx', 'index.html',
        'src/index.js', 'src/main.py', 'src/App.js', 'src/App.tsx'
    ]
    files_read = 0
    for main_file in main_files:
        if files_read >= 3:  # Limit to 3 main files
            break
        main_path = pathlib.Path(project_root) / main_file
        if main_path.exists():
            try:
                content = main_path.read_text(encoding='utf-8')[:2000]
                context_parts.append(f"MAIN FILE ({main_file}):\n{content}")
                ui.success(f"Read {main_file}")
                files_read += 1
            except Exception:
                pass

    # Combine all context
    full_context = "\n\n" + "="*50 + "\n\n".join(context_parts)

    ui.message("")
    ui.success(f"Project discovery complete! Found {len(context_parts)} key items.")
    ui.message("")

    return {"project_context": full_context}


def planner_agent(state: GraphState) -> GraphState:
    user_prompt = state["user_prompt"]
    mode = state.get("mode", "build")
    edit_instruction = state.get("edit_instruction")
    project_context = state.get("project_context")

    with ui.spinner("Planning project..."):
        resp = llm.with_structured_output(Plan, method="function_calling").invoke(
            planner_prompt(user_prompt, mode=mode, edit_instruction=edit_instruction, project_context=project_context)
        )
    if resp is None:
        ui.error("Planner did not return a valid response.")
        raise ValueError("Planner did not return a valid response.")

    # Set up project directory based on mode
    if mode == "build":
        # Build mode: create new project directory
        project_path = set_project_root(resp.name)
    else:
        # Edit mode: use existing project root
        from agent.tools import _project_root as project_root_module
        project_root_module = pathlib.Path(state["project_root"])
        # Set the global project root to the existing directory
        import agent.tools
        agent.tools._project_root = project_root_module
        project_path = project_root_module

    # Display the plan in a professional format
    ui.divider()
    ui.header("Project Plan")
    ui.message("")

    # Project Overview Box
    ui.message("┌─────────────────────────────────────────────────────────────┐")
    ui.message(f"│  [bold cyan]📋 {resp.name}[/bold cyan]")
    ui.message(f"│  [dim]{resp.description}[/dim]")
    ui.message("├─────────────────────────────────────────────────────────────┤")
    ui.message(f"│  [yellow]Tech Stack:[/yellow] {resp.techstack}")
    ui.message(f"│  [yellow]Location:[/yellow] {project_path}")
    ui.message("└─────────────────────────────────────────────────────────────┘")
    ui.message("")

    # Features Section
    if resp.features:
        ui.message("[bold yellow]🎯 FEATURES[/bold yellow]")
        ui.message("")
        for i, feature in enumerate(resp.features, 1):
            ui.message(f"  [green]✓[/green] {feature}")
        ui.message("")

    # Files Section - grouped by directory
    if resp.files:
        title = "📂 FILES TO MODIFY" if mode == "edit" else "📂 FILES TO CREATE"
        ui.message(f"[bold yellow]{title}[/bold yellow]")
        ui.message("")

        # Group files by directory
        from collections import defaultdict
        file_groups = defaultdict(list)
        for file in resp.files:
            parts = file.path.replace("\\", "/").split("/")
            if len(parts) > 1:
                dir_name = "/".join(parts[:-1])
            else:
                dir_name = "root"
            file_groups[dir_name].append(file)

        for dir_name, files in file_groups.items():
            ui.message(f"  [cyan]{dir_name}/[/cyan]")
            for file in files:
                filename = file.path.split("/")[-1]
                ui.message(f"    [green]→[/green] {filename}")
                ui.message(f"      [dim]{file.purpose}[/dim]")
            ui.message("")

    # Clear edit instruction after processing
    return {"plan": resp, "edit_instruction": None}


def architect_agent(state: GraphState) -> GraphState:
    plan: Plan = state["plan"]
    mode = state.get("mode", "build")
    edit_instruction = state.get("edit_instruction")
    project_context = state.get("project_context")

    with ui.spinner("Designing architecture..."):
        resp = llm.with_structured_output(TaskPlan, method="function_calling").invoke(
            architect_prompt(plan=plan.model_dump_json(), mode=mode, edit_instruction=edit_instruction, project_context=project_context)
        )
    if resp is None:
        ui.error("Architect did not return a valid response.")
        raise ValueError("Architect did not return a valid response.")

    # Display task plan grouped by module/feature
    ui.divider()
    ui.header("Implementation Plan")
    ui.message("")

    # Group tasks by directory/module
    from collections import defaultdict
    groups = defaultdict(list)

    for step in resp.implementation_steps:
        # Extract module from path (e.g., "backend/models" or "frontend/components")
        parts = step.filepath.replace("\\", "/").split("/")
        if len(parts) >= 2:
            # Group by first two parts (e.g., "backend/models")
            module = "/".join(parts[:2]) if len(parts) > 2 else parts[0]
        else:
            module = "Core"
        groups[module].append(step)

    # Display grouped tasks
    task_num = 1
    for module, tasks in groups.items():
        # Module header
        ui.message(f"[bold yellow]📁 {module.upper()}[/bold yellow]")
        ui.message("")

        for step in tasks:
            filename = step.filepath.split("/")[-1]
            ui.message(f"  [cyan]{task_num}.[/cyan] [green]{filename}[/green]")
            # Show description in a cleaner way
            desc_lines = step.task_description.split(". ")
            for line in desc_lines[:2]:  # Show first 2 sentences
                if line.strip():
                    ui.message(f"     [dim]{line.strip()}.[/dim]")
            task_num += 1

        ui.message("")

    ui.message(f"[bold]Total: {len(resp.implementation_steps)} tasks across {len(groups)} modules[/bold]")

    # Clear edit instruction after processing
    return {"task_plan": resp, "edit_instruction": None}


def coder_agent(state: GraphState) -> GraphState:
    coder_state: CoderState | None = state.get("coder_state")
    mode = state.get("mode", "build")

    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps
    total_steps = len(steps)

    if coder_state.current_step_idx >= total_steps:
        # Show project summary
        ui.divider()
        ui.header("Project Summary")
        ui.message("")

        plan = state.get("plan")
        if plan:
            ui.message(f"[bold green]✓ {plan.name}[/bold green] has been built!")
            ui.message("")
            ui.message(f"[bold]Tech Stack:[/bold] {plan.techstack}")
            ui.message("")

            if plan.features:
                ui.message("[bold]What was implemented:[/bold]")
                for feature in plan.features:
                    ui.message(f"  [green]✓[/green] {feature}")
                ui.message("")

        ui.message(f"[bold]Files created/modified:[/bold] {total_steps}")
        ui.message("")

        ui.success("All tasks completed!")
        return {"coder_state": coder_state, "status": "DONE"}

    current_idx = coder_state.current_step_idx
    current_task = steps[current_idx]

    # Show progress
    ui.divider()
    ui.message(f"[bold cyan]Step {current_idx + 1}/{total_steps}:[/bold cyan] {current_task.filepath}")

    # Persistent messages stored in GraphState
    messages = state.get("messages") or [
        SystemMessage(content=coder_system_prompt(mode=mode)),
        HumanMessage(content=f"Original request:\n{state['user_prompt']}"),
    ]

    # Read existing content
    existing_content = read_file.run(current_task.filepath)
    if existing_content:
        ui.info(f"Reading existing file: {current_task.filepath}")

    step_prompt = (
        f"Original request:\n{state['user_prompt']}\n\n"
        f"Current task:\n{current_task.task_description}\n"
        f"File: {current_task.filepath}\n\n"
        f"Existing content:\n{existing_content}\n\n"
        "Before writing, read any related files to keep selectors/functions consistent.\n"
        "Use write_file(path, content) to save changes."
    )

    messages_in = messages + [HumanMessage(content=step_prompt)]

    # Stream the agent's response
    ui.message("[dim]Thinking...[/dim]")
    updated_messages = list(messages_in)
    current_text = ""

    for chunk in react_agent.stream({"messages": messages_in}):
        # Handle different chunk types from the ReAct agent
        if "agent" in chunk:
            agent_messages = chunk["agent"].get("messages", [])
            for msg in agent_messages:
                if isinstance(msg, AIMessage):
                    # Stream text content
                    if msg.content and isinstance(msg.content, str):
                        # Only print new content
                        new_content = msg.content[len(current_text):]
                        if new_content:
                            ui.stream_text(new_content)
                            current_text = msg.content

                    # Show tool calls
                    if msg.tool_calls:
                        if current_text:
                            ui.stream_end()
                            current_text = ""
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.get("name", "unknown")
                            tool_args = tool_call.get("args", {})
                            if tool_name == "write_file":
                                ui.info(f"Writing: {tool_args.get('path', 'file')}")
                            elif tool_name == "edit_file":
                                ui.info(f"Editing: {tool_args.get('path', 'file')}")
                            elif tool_name == "read_file":
                                ui.info(f"Reading: {tool_args.get('path', 'file')}")
                            elif tool_name == "run_cmd":
                                ui.info(f"Running: {tool_args.get('cmd', 'command')[:50]}...")
                            elif tool_name == "list_files":
                                ui.info(f"Listing: {tool_args.get('directory', '.')}")
                            elif tool_name == "glob_files":
                                ui.info(f"Globbing: {tool_args.get('pattern', '*')}")
                            elif tool_name == "grep":
                                ui.info(f"Searching: {tool_args.get('pattern', '')}")
                            else:
                                ui.info(f"Tool: {tool_name}")

                    updated_messages.append(msg)

        elif "tools" in chunk:
            # Tool results
            tool_messages = chunk["tools"].get("messages", [])
            for msg in tool_messages:
                if isinstance(msg, ToolMessage):
                    updated_messages.append(msg)

    if current_text:
        ui.stream_end()

    # Show what was written
    ui.success(f"Completed: {current_task.filepath}")

    coder_state.current_step_idx += 1
    return {"coder_state": coder_state, "messages": updated_messages}


def clarifier_agent(state: GraphState) -> GraphState:
    """Check if prompt is vague and ask clarification questions if needed."""
    user_prompt = state["user_prompt"]

    # Heuristics to check if prompt is vague
    is_vague = False
    tech_keywords = [
        "python", "javascript", "typescript", "react", "vue", "angular", "node",
        "django", "flask", "fastapi", "express", "html", "css", "sql", "mongodb",
        "postgresql", "mysql", "java", "c++", "c#", "ruby", "php", "go", "rust"
    ]

    word_count = len(user_prompt.split())
    has_tech_stack = any(keyword in user_prompt.lower() for keyword in tech_keywords)
    has_generic_phrases = any(phrase in user_prompt.lower() for phrase in [
        "create app", "make app", "build app", "new app", "simple app"
    ])

    # Vague if: short prompt, no tech stack, or very generic
    if word_count < 10 or (not has_tech_stack and has_generic_phrases):
        is_vague = True

    if not is_vague:
        # Prompt is clear enough, proceed to planning
        return {"status": "PLANNING"}

    # Prompt is vague, ask for clarifications
    ui.warning("Your request needs some clarification...")

    clarification_prompt = f"""
The user provided this vague request: "{user_prompt}"

Generate EXACTLY 3 clarification questions to help understand the project better:
1. What is the main purpose/goal of this project?
2. What are the key features or functionalities needed?
3. Any specific requirements or constraints?

DO NOT ask about technology stack - that will be decided later.
Keep questions concise, friendly, and practical.
Generate exactly 3 questions, no more, no less.
"""

    with ui.spinner("Generating clarification questions..."):
        try:
            clarification_req = llm.with_structured_output(
                ClarificationRequest, method="function_calling"
            ).invoke(clarification_prompt)
        except Exception:
            # If clarification generation fails, proceed without it
            ui.warning("Failed to generate clarifications, proceeding with original prompt")
            return {"status": "PLANNING"}

    if not clarification_req or not clarification_req.questions:
        return {"status": "PLANNING"}

    # Limit to max 3 questions
    questions = clarification_req.questions[:3]

    # Display questions and collect answers
    ui.header("Clarification Questions")
    ui.message(f"[dim]{clarification_req.reason}[/dim]")
    ui.message("")
    ui.message("[dim]Tip: Press Enter to skip any question (I'll decide for you)[/dim]")
    ui.message("")  # blank line

    answers = []
    for i, question in enumerate(questions, 1):
        ui.message(f"[bold cyan]Q{i}.[/bold cyan] {question}")
        ui.message("")  # Space before answer prompt
        answer = ui.prompt(f"   [cyan]A{i}:[/cyan] ").strip()
        if not answer:
            answer = "(You decide based on best practices)"
            ui.message(f"   [dim]→ I'll decide this for you[/dim]")
        answers.append(answer)
        ui.message("")  # blank line after answer

    # Construct enhanced prompt
    qa_text = "\n".join([
        f"Q: {q}\nA: {a}"
        for q, a in zip(questions, answers)
    ])

    enhanced_prompt = f"""{user_prompt}

Additional context from clarification:
{qa_text}
"""

    ui.success("Clarifications collected!")

    return {
        "user_prompt": enhanced_prompt,
        "clarification_questions": questions,
        "clarification_answers": answers,
        "status": "PLANNING"
    }


def planner_confirm_node(state: GraphState) -> GraphState:
    """Ask user to confirm, edit, or cancel the plan."""
    ui.divider()
    ui.header("Plan Review")
    ui.message("")
    ui.message("[bold]Does this plan look good?[/bold]")
    ui.message("")
    ui.message("[green]1)[/green] ✓ Proceed - looks good, start implementation")
    ui.message("[yellow]2)[/yellow] ✎ Edit - I want to change something")
    ui.message("[red]3)[/red] ✗ Cancel - start over")
    ui.message("")

    choice = ui.prompt("[bold cyan]Your choice [1-3]:[/bold cyan] ").strip()

    if choice == "1":
        return {"status": "PLANNING"}
    elif choice == "2":
        ui.message("")
        edit_instruction = ui.prompt("[cyan]What changes would you like?[/cyan] ").strip()
        if edit_instruction:
            return {"edit_instruction": edit_instruction}
        else:
            ui.message("")
            ui.warning("No changes provided, proceeding with current plan")
            return {"status": "PLANNING"}
    elif choice == "3":
        ui.message("")
        ui.warning("Plan cancelled by user")
        return {"status": "CANCELLED"}
    else:
        ui.message("")
        ui.warning("Invalid choice, proceeding with plan")
        return {"status": "PLANNING"}


def architect_confirm_node(state: GraphState) -> GraphState:
    """Ask user to confirm, edit, or cancel the architecture."""
    ui.divider()
    ui.header("Ready to Build")
    ui.message("")
    ui.message("[bold]Ready to start coding?[/bold]")
    ui.message("")
    ui.message("[green]1)[/green] ✓ Start - begin implementation")
    ui.message("[yellow]2)[/yellow] ✎ Modify - change the task plan")
    ui.message("[red]3)[/red] ✗ Cancel - start over")
    ui.message("")

    choice = ui.prompt("[bold cyan]Your choice [1-3]:[/bold cyan] ").strip()

    if choice == "1":
        return {"status": "ARCHITECTING"}
    elif choice == "2":
        ui.message("")
        edit_instruction = ui.prompt("[cyan]What changes would you like?[/cyan] ").strip()
        if edit_instruction:
            return {"edit_instruction": edit_instruction}
        else:
            ui.message("")
            ui.warning("No changes provided, proceeding with current architecture")
            return {"status": "ARCHITECTING"}
    elif choice == "3":
        ui.message("")
        ui.warning("Architecture cancelled by user")
        return {"status": "CANCELLED"}
    else:
        ui.message("")
        ui.warning("Invalid choice, proceeding with architecture")
        return {"status": "ARCHITECTING"}


def route_planner_confirmation(state: GraphState) -> str:
    """Route based on planner confirmation response."""
    status = state.get("status")
    edit_instruction = state.get("edit_instruction")

    if status == "CANCELLED":
        return "cancel"
    elif edit_instruction:
        return "edit"
    else:
        return "proceed"


def route_architect_confirmation(state: GraphState) -> str:
    """Route based on architect confirmation response."""
    status = state.get("status")
    edit_instruction = state.get("edit_instruction")

    if status == "CANCELLED":
        return "cancel"
    elif edit_instruction:
        return "edit"
    else:
        return "proceed"


graph = StateGraph(GraphState)
graph.add_node("clarifier", clarifier_agent)
graph.add_node("discover", discover_project)
graph.add_node("planner", planner_agent)
graph.add_node("planner_confirm", planner_confirm_node)
graph.add_node("architect", architect_agent)
graph.add_node("architect_confirm", architect_confirm_node)
graph.add_node("coder", coder_agent)

# Graph flow with discovery, clarification and confirmations:
# clarifier → discover → planner → planner_confirm → (proceed: architect | edit: planner | cancel: END)
# architect → architect_confirm → (proceed: coder | edit: architect | cancel: END)
# coder → (DONE: END | continue: coder)

graph.add_edge("clarifier", "discover")
graph.add_edge("discover", "planner")
graph.add_edge("planner", "planner_confirm")
graph.add_conditional_edges(
    "planner_confirm",
    route_planner_confirmation,
    {"proceed": "architect", "edit": "planner", "cancel": END}
)

graph.add_edge("architect", "architect_confirm")
graph.add_conditional_edges(
    "architect_confirm",
    route_architect_confirmation,
    {"proceed": "coder", "edit": "architect", "cancel": END}
)

graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"},
)

graph.set_entry_point("clarifier")
agent = graph.compile()
