#!/usr/bin/env python3
"""Coder Buddy - AI-powered coding assistant with beautiful terminal UI."""

import argparse
import sys
import traceback

from agent.graph import agent
from agent.ui import ui


def handle_command(command: str, current_mode: str, current_permission: str, current_project_root: str = ".") -> bool | str:
    """Handle slash commands. Returns True if should continue REPL."""
    cmd = command.lower().strip()

    if cmd in ("/exit", "/quit", "/q"):
        ui.message("[dim]Goodbye![/dim]")
        return False

    elif cmd in ("/clear", "/c"):
        ui.console.clear()
        ui.welcome()
        return True

    elif cmd in ("/help", "/h", "/?"):
        ui.header("Commands")
        ui.message("[cyan]/new[/cyan]     - Start a new project (re-select mode)")
        ui.message("[cyan]/status[/cyan]  - Show current mode and settings")
        ui.message("[cyan]/clear[/cyan]   - Clear the screen")
        ui.message("[cyan]/help[/cyan]    - Show this help message")
        ui.message("[cyan]/exit[/cyan]    - Exit the application")
        ui.message("")
        ui.header("Modes")
        ui.message("[green]Build Mode[/green] - Create new projects from scratch")
        ui.message("[yellow]Edit Mode[/yellow] - Modify existing projects")
        ui.message("")
        ui.message("[dim]Use /new to switch between modes at any time![/dim]")
        return True

    elif cmd in ("/status", "/s"):
        ui.header("Current Settings")
        mode_name = "Build Mode" if current_mode == "build" else "Edit Mode"
        perm_name = "Strict (asks confirmations)" if current_permission == "strict" else "Permissive (no confirmations)"
        ui.message(f"[cyan]Mode:[/cyan] {mode_name}")
        if current_mode == "edit":
            ui.message(f"[cyan]Project Root:[/cyan] {current_project_root}")
        ui.message(f"[cyan]Permissions:[/cyan] {perm_name}")
        return True

    elif cmd in ("/new", "/n", "/restart"):
        ui.message("")
        ui.message("[dim]Starting fresh...[/dim]")
        ui.message("")
        return "restart"  # Signal to restart mode selection

    else:
        ui.warning(f"Unknown command: {command}")
        ui.message("[dim]Type /help for available commands[/dim]")
        return True


def chat_about_project(plan, task_plan, project_root: str) -> str:
    """
    Chat with LLM about the project. Returns action: 'continue', 'new', or 'exit'.
    """
    from agent.llm import chat_llm
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    # Build project context for the chat
    context = f"""You are a helpful assistant chatting about a project that was just built/modified.

PROJECT DETAILS:
- Name: {plan.name}
- Description: {plan.description}
- Tech Stack: {plan.techstack}
- Features: {', '.join(plan.features)}

FILES CREATED/MODIFIED:
{chr(10).join([f"- {step.filepath}: {step.task_description[:100]}..." for step in task_plan.implementation_steps])}

PROJECT LOCATION: {project_root}

Answer questions about the project, explain how things work, suggest improvements, or help with any issues.
Keep responses concise but helpful.
"""

    llm = chat_llm
    messages = [SystemMessage(content=context)]

    ui.divider()
    ui.header("Chat Mode")
    ui.message("")
    ui.message("[bold]Ask me anything about your project![/bold]")
    ui.message("[dim]Type '/done' to exit chat, '/continue' to keep building, '/new' for new project[/dim]")
    ui.message("")

    while True:
        try:
            user_input = ui.prompt("[bold magenta]Chat>[/bold magenta] ").strip()

            if not user_input:
                continue

            # Handle chat commands
            if user_input.lower() == "/done":
                return "exit"
            elif user_input.lower() == "/continue":
                return "continue"
            elif user_input.lower() == "/new":
                return "new"
            elif user_input.lower() == "/help":
                ui.message("")
                ui.message("[cyan]/done[/cyan]     - Exit chat and finish")
                ui.message("[cyan]/continue[/cyan] - Continue building this project")
                ui.message("[cyan]/new[/cyan]      - Start a new project")
                ui.message("")
                continue

            # Chat with LLM
            messages.append(HumanMessage(content=user_input))

            ui.message("")
            response_text = ""
            for chunk in llm.stream(messages):
                if chunk.content:
                    ui.stream_text(chunk.content)
                    response_text += chunk.content
            ui.stream_end()
            ui.message("")

            messages.append(AIMessage(content=response_text))

        except KeyboardInterrupt:
            ui.message("")
            return "exit"
        except EOFError:
            return "exit"


def post_completion_menu(plan, task_plan, project_root: str, mode: str) -> str:
    """
    Show post-completion options and return action: 'continue', 'new', 'chat', or 'exit'.
    """
    ui.divider()
    ui.header("What's Next?")
    ui.message("")
    ui.message("[bold]Your project is ready! What would you like to do?[/bold]")
    ui.message("")
    ui.message("[cyan]1)[/cyan] [magenta]💬 Chat[/magenta] - Ask questions about the project")
    ui.message("[cyan]2)[/cyan] [yellow]🔧 Continue[/yellow] - Keep building on this project")
    ui.message("[cyan]3)[/cyan] [green]🆕 New Project[/green] - Start something new")
    ui.message("[cyan]4)[/cyan] [dim]👋 Exit[/dim] - Done for now")
    ui.message("")

    choice = ui.prompt("[bold cyan]Choice [1-4]:[/bold cyan] ").strip()

    if choice == "1":
        return "chat"
    elif choice == "2":
        return "continue"
    elif choice == "3":
        return "new"
    elif choice == "4":
        return "exit"
    else:
        ui.message("")
        ui.message("[dim]Defaulting to Exit...[/dim]")
        return "exit"


def show_run_instructions(plan, project_root: str, mode: str) -> None:
    """Show run instructions based on project type and offer to run."""
    import subprocess
    import os

    tech_stack = plan.techstack.lower() if plan.techstack else ""
    project_name = plan.name

    # Detect project type and determine run commands
    run_commands = []
    install_commands = []

    # Determine the actual project directory
    if mode == "build":
        # In build mode, project is in a subdirectory
        from agent.tools import get_project_root
        try:
            actual_root = str(get_project_root())
        except:
            actual_root = project_root
    else:
        actual_root = project_root

    # HTML/CSS/JS (static) - check FIRST before Node.js to avoid false matches
    # A project with "HTML, CSS, JavaScript" is static, not Node.js
    is_static_html = any(x in tech_stack for x in ["html", "css", "vanilla"])
    is_node_project = any(x in tech_stack for x in ["node", "react", "next", "express", "typescript"])

    if is_static_html and not is_node_project:
        import platform
        if platform.system() == "Windows":
            run_commands = ["start index.html"]
        elif platform.system() == "Darwin":  # macOS
            run_commands = ["open index.html"]
        else:  # Linux
            run_commands = ["xdg-open index.html"]

    # Node.js / React / Next.js
    elif is_node_project or ("javascript" in tech_stack and not is_static_html):
        install_commands = ["npm install"]
        if "react" in tech_stack or "next" in tech_stack:
            run_commands = ["npm start", "npm run dev"]
        else:
            run_commands = ["npm start", "node index.js", "node server.js"]

    # Python / Flask / Django / FastAPI
    elif any(x in tech_stack for x in ["python", "flask", "django", "fastapi"]):
        install_commands = ["pip install -r requirements.txt"]
        if "flask" in tech_stack:
            run_commands = ["python app.py", "flask run"]
        elif "django" in tech_stack:
            run_commands = ["python manage.py runserver"]
        elif "fastapi" in tech_stack:
            run_commands = ["uvicorn main:app --reload"]
        else:
            run_commands = ["python main.py", "python app.py"]

    # Go
    elif "go" in tech_stack:
        run_commands = ["go run main.go", "go run ."]

    # Rust
    elif "rust" in tech_stack:
        install_commands = ["cargo build"]
        run_commands = ["cargo run"]

    # Show instructions
    ui.divider()
    ui.header("How to Run Your Project")
    ui.message("")

    # Project location box
    ui.message("┌─────────────────────────────────────────────────────────────┐")
    ui.message(f"│  [bold cyan]📂 Project Location[/bold cyan]")
    ui.message(f"│  [green]{actual_root}[/green]")
    ui.message("└─────────────────────────────────────────────────────────────┘")
    ui.message("")

    # Step-by-step instructions
    ui.message("[bold]📋 STEP-BY-STEP INSTRUCTIONS[/bold]")
    ui.message("")

    step_num = 1

    # Always show cd command first for server projects
    if install_commands or (run_commands and not any(x in tech_stack for x in ["html", "css", "vanilla"])):
        ui.message(f"[yellow]{step_num}.[/yellow] [bold]Open Terminal & Navigate to Project:[/bold]")
        ui.message(f"   [dim]Copy and paste this command:[/dim]")
        ui.message(f"   [green]cd {actual_root}[/green]")
        ui.message("")
        step_num += 1

    if install_commands:
        ui.message(f"[yellow]{step_num}.[/yellow] [bold]Install Dependencies:[/bold]")
        ui.message(f"   [dim]This downloads all required packages[/dim]")
        for cmd in install_commands:
            ui.message(f"   [green]{cmd}[/green]")
        ui.message("")
        step_num += 1

    if run_commands:
        if is_static_html and not is_node_project:
            ui.message(f"[yellow]{step_num}.[/yellow] [bold]Open in Browser:[/bold]")
            ui.message(f"   [dim]Double-click the file or run:[/dim]")
            ui.message(f"   [green]{run_commands[0]}[/green]")
        else:
            ui.message(f"[yellow]{step_num}.[/yellow] [bold]Start the Server:[/bold]")
            ui.message(f"   [dim]Run one of these commands:[/dim]")
            for cmd in run_commands:
                ui.message(f"   [green]{cmd}[/green]")
            ui.message("")
            ui.message(f"   [dim]Press Ctrl+C to stop the server when done[/dim]")
        ui.message("")

    # Quick copy-paste section
    if install_commands or run_commands:
        ui.message("[bold]⚡ QUICK START (Copy & Paste All)[/bold]")
        ui.message("")
        all_commands = [f"cd {actual_root}"]
        all_commands.extend(install_commands)
        if run_commands:
            all_commands.append(run_commands[0])
        ui.message(f"   [green]{' && '.join(all_commands)}[/green]")
        ui.message("")

    # Offer to run
    if install_commands or run_commands:
        ui.divider()
        ui.message("")

        if is_static_html and not is_node_project:
            if ui.confirm("[bold cyan]Would you like me to open the project in your browser?[/bold cyan]"):
                ui.message("")
                original_dir = os.getcwd()
                try:
                    os.chdir(actual_root)
                    main_cmd = run_commands[0]
                    ui.info(f"Opening: {main_cmd}")

                    try:
                        subprocess.run(main_cmd, shell=True)
                        ui.success("Opened in browser!")
                    except Exception as e:
                        ui.error(f"Could not open browser: {e}")
                        ui.message(f"[dim]Try opening manually: {actual_root}/index.html[/dim]")
                finally:
                    os.chdir(original_dir)
            else:
                ui.message("")
                ui.message(f"[dim]Open {actual_root}/index.html in your browser when ready.[/dim]")
        else:
            # Server-based project
            if ui.confirm("[bold cyan]Would you like me to run the project now?[/bold cyan]"):
                ui.message("")

                # Change to project directory
                original_dir = os.getcwd()
                try:
                    os.chdir(actual_root)

                    # Run install commands first
                    if install_commands:
                        for cmd in install_commands:
                            ui.info(f"Running: {cmd}")
                            try:
                                result = subprocess.run(
                                    cmd, shell=True, capture_output=True, text=True, timeout=120
                                )
                                if result.returncode == 0:
                                    ui.success(f"✓ {cmd} completed")
                                    if result.stdout:
                                        ui.message(f"[dim]{result.stdout[:500]}[/dim]")
                                else:
                                    ui.error(f"✗ {cmd} failed")
                                    if result.stderr:
                                        ui.message(f"[red]{result.stderr[:500]}[/red]")
                                    ui.message("")
                                    ui.message("[dim]You can try running the commands manually.[/dim]")
                                    return
                            except subprocess.TimeoutExpired:
                                ui.warning(f"Command timed out: {cmd}")
                            except Exception as e:
                                ui.error(f"Error running {cmd}: {e}")

                    # Run the main command
                    if run_commands:
                        main_cmd = run_commands[0]
                        ui.message("")
                        ui.info(f"Starting: {main_cmd}")
                        ui.message("[dim]Press Ctrl+C to stop the server[/dim]")
                        ui.message("")

                        try:
                            # Run interactively so user can see output and stop it
                            subprocess.run(main_cmd, shell=True)
                        except KeyboardInterrupt:
                            ui.message("")
                            ui.success("Server stopped")
                        except Exception as e:
                            ui.error(f"Error: {e}")

                finally:
                    os.chdir(original_dir)
            else:
                ui.message("")
                ui.message("[dim]You can run the commands above manually when ready.[/dim]")


def select_mode_interactive() -> tuple[str, str]:
    """
    Ask user to select mode interactively.
    Returns: (mode, project_root)
    """
    import os

    ui.divider()
    ui.header("Getting Started")
    ui.message("")
    ui.message("[bold]What would you like to do?[/bold]")
    ui.message("")
    ui.message("[cyan]1)[/cyan] [green]Build a new project[/green] - Start from scratch")
    ui.message("[cyan]2)[/cyan] [yellow]Edit an existing project[/yellow] - Modify existing code")
    ui.message("")

    choice = ui.prompt("[bold cyan]Choice [1-2]:[/bold cyan] ").strip()

    if choice == "2":
        # Edit mode - search for project folder
        ui.message("")
        ui.message("[bold]Enter the name of your project folder:[/bold]")
        ui.message("[dim]I'll search for it in the current directory and subdirectories[/dim]")
        ui.message("[dim]Example: 'my-app' or 'todolistapp'[/dim]")
        ui.message("")

        while True:
            folder_name = ui.prompt("   [cyan]Project folder name:[/cyan] ").strip()

            if not folder_name:
                ui.warning("Folder name cannot be empty. Please try again.")
                ui.message("")
                continue

            # Search for the folder
            ui.message("")
            with ui.spinner(f"Searching for '{folder_name}'..."):
                current_dir = os.getcwd()
                matches = []

                # Search in current directory and one level deep
                for root, dirs, files in os.walk(current_dir):
                    # Only go one level deep
                    depth = root[len(current_dir):].count(os.sep)
                    if depth > 1:
                        continue

                    if folder_name in dirs:
                        full_path = os.path.join(root, folder_name)
                        matches.append(full_path)

            if not matches:
                ui.error(f"Could not find folder '{folder_name}' in current directory or subdirectories")
                ui.message("")
                retry = ui.confirm("Try a different name?")
                if not retry:
                    ui.message("")
                    ui.message("[dim]Falling back to Build mode...[/dim]")
                    return ("build", ".")
                ui.message("")
                continue

            # If multiple matches, let user choose
            if len(matches) > 1:
                ui.message("")
                ui.message(f"[yellow]Found {len(matches)} folders named '{folder_name}':[/yellow]")
                ui.message("")
                for i, path in enumerate(matches, 1):
                    ui.message(f"  [cyan]{i})[/cyan] {path}")
                ui.message("")

                choice_idx = ui.prompt("   [cyan]Select folder [1-{}]:[/cyan] ".format(len(matches))).strip()
                try:
                    idx = int(choice_idx) - 1
                    if 0 <= idx < len(matches):
                        project_path = matches[idx]
                    else:
                        ui.warning("Invalid choice, using first match")
                        project_path = matches[0]
                except ValueError:
                    ui.warning("Invalid input, using first match")
                    project_path = matches[0]
            else:
                project_path = matches[0]

            ui.message("")
            ui.success(f"Edit mode enabled for: {project_path}")
            return ("edit", project_path)

    else:
        # Build mode (default for any other input including "1")
        if choice != "1":
            ui.message("")
            ui.message("[dim]Defaulting to Build mode...[/dim]")
        else:
            ui.message("")
            ui.success("Build mode selected - ready to create a new project!")
        return ("build", ".")


def run_agent(user_prompt: str, recursion_limit: int, mode: str = "build",
               project_root: str = ".", permission_mode: str = "strict") -> dict | None:
    """Run the agent with the given prompt. Returns result dict or None."""
    from agent.tools import set_permission_mode

    # Set permission mode
    set_permission_mode(permission_mode)

    try:
        result = agent.invoke(
            {
                "user_prompt": user_prompt,
                "mode": mode,
                "project_root": project_root,
                "permission_mode": permission_mode,
            },
            {"recursion_limit": recursion_limit}
        )

        ui.header("Complete")
        status = result.get("status", "UNKNOWN")

        if status == "DONE":
            ui.success("Project generated successfully!")
            # Only show files when actually completed
            task_plan = result.get("task_plan")
            if task_plan:
                files_created = [step.filepath for step in task_plan.implementation_steps]
                ui.file_tree(files_created, title="Generated Files")

            # Show run instructions and offer to run
            plan = result.get("plan")
            if plan:
                show_run_instructions(plan, project_root, mode)

            return result  # Return for post-completion options

        elif status == "CANCELLED":
            ui.warning("Operation cancelled by user")
            ui.message("")
            ui.message("[dim]Your project was not modified.[/dim]")
            return None
        else:
            ui.warning(f"Status: {status}")
            return None

    except KeyboardInterrupt:
        ui.warning("Operation cancelled")
        return None
    except Exception as e:
        ui.error(f"Error: {e}")
        if ui.confirm("Show traceback?"):
            traceback.print_exc()
        return None


def repl(recursion_limit: int, mode: str = "build",
         project_root: str = ".", permission_mode: str = "strict",
         interactive_mode_selection: bool = False) -> None:
    """Interactive REPL loop."""
    ui.welcome()

    # If interactive mode selection enabled, ask user
    if interactive_mode_selection:
        mode, project_root = select_mode_interactive()
        ui.divider()

    # Show mode/permission info if non-default or edit mode
    if mode == "edit" or permission_mode != "strict":
        if mode == "edit":
            ui.info(f"[bold]Edit Mode:[/bold] Modifying existing project at {project_root}")
        if permission_mode == "permissive":
            ui.info(f"[bold]Permissions:[/bold] Permissive (no confirmations)")
        ui.divider()

    # Track current project context for continuation
    current_result = None
    current_project_root = project_root

    while True:
        try:
            user_input = ui.prompt("[bold cyan]>[/bold cyan] ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                result = handle_command(user_input, mode, permission_mode, current_project_root)
                if result == False:
                    break
                elif result == "restart":
                    # Restart mode selection
                    mode, project_root = select_mode_interactive()
                    current_project_root = project_root
                    current_result = None
                    ui.divider()
                    if mode == "edit":
                        ui.info(f"[bold]Edit Mode:[/bold] Modifying existing project at {project_root}")
                        ui.divider()
                continue

            # Run the agent
            result = run_agent(user_input, recursion_limit, mode, current_project_root, permission_mode)

            # Handle post-completion options if project was completed
            if result and result.get("status") == "DONE":
                plan = result.get("plan")
                task_plan = result.get("task_plan")

                # Get the actual project root (might have changed in build mode)
                if mode == "build" and plan:
                    from agent.tools import get_project_root
                    try:
                        current_project_root = str(get_project_root())
                    except:
                        pass

                current_result = result

                # Show post-completion menu
                if plan and task_plan:
                    action = post_completion_menu(plan, task_plan, current_project_root, mode)

                    if action == "chat":
                        # Enter chat mode
                        chat_action = chat_about_project(plan, task_plan, current_project_root)
                        if chat_action == "continue":
                            # Switch to edit mode on current project
                            mode = "edit"
                            ui.divider()
                            ui.info(f"[bold]Edit Mode:[/bold] Continuing work on {current_project_root}")
                            ui.message("[dim]Enter your next request:[/dim]")
                            ui.message("")
                        elif chat_action == "new":
                            mode, project_root = select_mode_interactive()
                            current_project_root = project_root
                            current_result = None
                            ui.divider()
                        else:  # exit
                            ui.message("")
                            ui.message("[dim]Goodbye![/dim]")
                            break

                    elif action == "continue":
                        # Switch to edit mode on current project
                        mode = "edit"
                        ui.divider()
                        ui.info(f"[bold]Edit Mode:[/bold] Continuing work on {current_project_root}")
                        ui.message("[dim]Enter your next request:[/dim]")
                        ui.message("")

                    elif action == "new":
                        mode, project_root = select_mode_interactive()
                        current_project_root = project_root
                        current_result = None
                        ui.divider()

                    else:  # exit
                        ui.message("")
                        ui.message("[dim]Goodbye![/dim]")
                        break
                else:
                    ui.divider()
            else:
                ui.divider()

        except KeyboardInterrupt:
            ui.message("\n[dim]Press Ctrl+C again to exit, or type /exit[/dim]")
            try:
                user_input = ui.prompt("> ").strip()
                if user_input.lower() in ("/exit", "/quit", "/q"):
                    break
            except KeyboardInterrupt:
                ui.message("\n[dim]Goodbye![/dim]")
                break
        except EOFError:
            break


def main():
    import os

    parser = argparse.ArgumentParser(
        description="Coder Buddy - AI-powered coding assistant"
    )
    parser.add_argument(
        "--recursion-limit", "-r",
        type=int,
        default=100,
        help="Recursion limit for agent processing (default: 100)"
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default=None,
        help="Run with a single prompt instead of interactive mode"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["build", "edit"],
        default="build",
        help="Mode: 'build' creates new project, 'edit' modifies existing (default: build)"
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Project root path for edit mode (default: current directory)"
    )
    parser.add_argument(
        "--permission",
        type=str,
        choices=["strict", "permissive"],
        default="strict",
        help="Permission mode: 'strict' asks for confirmations, 'permissive' allows all (default: strict)"
    )
    args = parser.parse_args()

    # Check if user explicitly set mode or root
    # If not, we'll enable interactive mode selection in REPL
    mode_explicitly_set = any(arg in sys.argv for arg in ["--mode", "-m", "--root"])

    # Convert root to absolute path
    project_root = os.path.abspath(args.root)

    # Validate edit mode (only if explicitly set via CLI)
    if mode_explicitly_set and args.mode == "edit" and not os.path.isdir(project_root):
        ui.error(f"Project root does not exist: {project_root}")
        sys.exit(1)

    if args.prompt:
        # Single prompt mode - always respect CLI args
        run_agent(args.prompt, args.recursion_limit, args.mode, project_root, args.permission)
    else:
        # Interactive REPL mode
        # Enable interactive mode selection if user didn't set mode via CLI
        interactive_selection = not mode_explicitly_set
        repl(args.recursion_limit, args.mode, project_root, args.permission, interactive_selection)


if __name__ == "__main__":
    main()
