#!/usr/bin/env python3
"""Coder Buddy - AI-powered coding assistant with beautiful terminal UI."""

import argparse
import sys
import traceback

from agent.graph import agent
from agent.ui import ui


def handle_command(command: str) -> bool:
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
        ui.message("[cyan]/help[/cyan]    - Show this help message")
        ui.message("[cyan]/clear[/cyan]   - Clear the screen")
        ui.message("[cyan]/exit[/cyan]    - Exit the application")
        ui.message("")
        ui.message("[dim]Or just type your project request to get started![/dim]")
        return True

    else:
        ui.warning(f"Unknown command: {command}")
        ui.message("[dim]Type /help for available commands[/dim]")
        return True


def run_agent(user_prompt: str, recursion_limit: int) -> None:
    """Run the agent with the given prompt."""
    try:
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": recursion_limit}
        )

        ui.header("Complete")
        status = result.get("status", "UNKNOWN")

        if status == "DONE":
            ui.success("Project generated successfully!")
        else:
            ui.warning(f"Status: {status}")

        task_plan = result.get("task_plan")
        if task_plan:
            files_created = [step.filepath for step in task_plan.implementation_steps]
            ui.file_tree(files_created, title="Generated Files")

    except KeyboardInterrupt:
        ui.warning("Operation cancelled")
    except Exception as e:
        ui.error(f"Error: {e}")
        if ui.confirm("Show traceback?"):
            traceback.print_exc()


def repl(recursion_limit: int) -> None:
    """Interactive REPL loop."""
    ui.welcome()

    while True:
        try:
            user_input = ui.prompt("> ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                if not handle_command(user_input):
                    break
                continue

            # Run the agent
            run_agent(user_input, recursion_limit)
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
    args = parser.parse_args()

    if args.prompt:
        # Single prompt mode
        run_agent(args.prompt, args.recursion_limit)
    else:
        # Interactive REPL mode
        repl(args.recursion_limit)


if __name__ == "__main__":
    main()
