from __future__ import annotations

from dotenv import load_dotenv
from langchain_core.globals import set_debug, set_verbose
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent

from agent.prompts import architect_prompt, coder_system_prompt, planner_prompt
from agent.states import CoderState, GraphState, Plan, TaskPlan
from agent.tools import get_current_directory, list_files, read_file, write_file, run_cmd, set_project_root
from agent.ui import ui


_ = load_dotenv()
set_debug(False)  # Disable debug for cleaner output
set_verbose(False)

llm = ChatOpenAI(
    model="gpt-4o",  # or gpt-5.1 / gpt-5
    temperature=0,
    streaming=True,  # Enable streaming
)

# Include run_cmd for shell execution capability
coder_tools = [read_file, write_file, list_files, get_current_directory, run_cmd]
react_agent = create_react_agent(llm, coder_tools)


def planner_agent(state: GraphState) -> GraphState:
    user_prompt = state["user_prompt"]
    with ui.spinner("Planning project..."):
        resp = llm.with_structured_output(Plan, method="function_calling").invoke(
            planner_prompt(user_prompt)
        )
    if resp is None:
        ui.error("Planner did not return a valid response.")
        raise ValueError("Planner did not return a valid response.")

    # Set up project directory based on project name
    project_path = set_project_root(resp.name)

    # Display the plan
    ui.success(f"Project: {resp.name}")
    ui.info(f"Directory: {project_path}")
    ui.info(f"Tech Stack: {resp.techstack}")
    ui.message(f"[dim]{resp.description}[/dim]")
    if resp.files:
        ui.file_tree([f.path for f in resp.files], title="Files to Create")

    return {"plan": resp}


def architect_agent(state: GraphState) -> GraphState:
    plan: Plan = state["plan"]
    with ui.spinner("Designing architecture..."):
        resp = llm.with_structured_output(TaskPlan, method="function_calling").invoke(
            architect_prompt(plan=plan.model_dump_json())
        )
    if resp is None:
        ui.error("Architect did not return a valid response.")
        raise ValueError("Architect did not return a valid response.")

    # Display task plan as todos
    todos = [
        {"content": step.task_description[:60] + "..." if len(step.task_description) > 60 else step.task_description,
         "status": "pending",
         "activeForm": f"Working on {step.filepath}"}
        for step in resp.implementation_steps
    ]
    ui.todo_list(todos)

    return {"task_plan": resp}


def coder_agent(state: GraphState) -> GraphState:
    coder_state: CoderState | None = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps
    total_steps = len(steps)

    if coder_state.current_step_idx >= total_steps:
        ui.success("All tasks completed!")
        return {"coder_state": coder_state, "status": "DONE"}

    current_idx = coder_state.current_step_idx
    current_task = steps[current_idx]

    # Show progress
    ui.divider()
    ui.message(f"[bold cyan]Step {current_idx + 1}/{total_steps}:[/bold cyan] {current_task.filepath}")

    # Persistent messages stored in GraphState
    messages = state.get("messages") or [
        SystemMessage(content=coder_system_prompt()),
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
                            elif tool_name == "read_file":
                                ui.info(f"Reading: {tool_args.get('path', 'file')}")
                            elif tool_name == "run_cmd":
                                ui.info(f"Running: {tool_args.get('cmd', 'command')[:50]}...")
                            elif tool_name == "list_files":
                                ui.info(f"Listing: {tool_args.get('directory', '.')}")
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


graph = StateGraph(GraphState)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")

graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"},
)

graph.set_entry_point("planner")
agent = graph.compile()
