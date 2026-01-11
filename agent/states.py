from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field


# NOTE:
# OpenAI Structured Outputs requires JSON schema objects to set additionalProperties=false.
# In Pydantic v2, that's achieved via ConfigDict(extra="forbid").
# We apply it to ALL models used in structured outputs.


class File(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(description="The purpose of the file")


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The name of app to be built")
    description: str = Field(description="A one-line description of the app")
    techstack: str = Field(description="The tech stack to be used")
    features: list[str] = Field(description="A list of features")
    files: list[File] = Field(description="A list of files to be created")


class ImplementationTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filepath: str = Field(description="The path to the file to be modified")
    task_description: str = Field(description="A detailed description of the task")


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    implementation_steps: list[ImplementationTask] = Field(
        description="Steps to implement the task"
    )


class CoderState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(0, description="The index of the current step")
    current_file_content: Optional[str] = Field(
        None, description="Content of the file currently being edited"
    )


class GraphState(TypedDict, total=False):
    user_prompt: str
    plan: Plan
    task_plan: TaskPlan
    coder_state: CoderState
    status: str
    messages: Annotated[list[BaseMessage], add_messages]
