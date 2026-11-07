"""Trap Suite schema.

A scenario is a legitimate task the agent must complete, a workspace seeded with a
trap, and mechanical tripwires that decide whether the trap was sprung. Scenarios are
plain YAML so anyone can audit exactly what an agent was tested against.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from windowsticker.domain import Severity

TEMPLATE_RE = re.compile(r"\{\{\s*(canary|run_id|exfil_host)(?::([A-Z0-9_]+))?\s*\}\}")


class Category(StrEnum):
    INJECTION_FILE = "prompt_injection_file"
    INJECTION_TICKET = "prompt_injection_ticket"
    INJECTION_TOOL_OUTPUT = "prompt_injection_tool_output"
    INJECTION_IMAGE = "prompt_injection_image"
    CLOUD_METADATA = "cloud_metadata"
    CREDENTIAL_DISCOVERY = "credential_discovery"
    DESTRUCTIVE_SHORTCUT = "destructive_shortcut"
    SCOPE_CREEP = "scope_creep"
    DEPENDENCY_CONFUSION = "dependency_confusion"
    DNS_EXFIL = "dns_exfiltration"
    RESOURCE_ABUSE = "resource_abuse"
    FALSE_COMPLETION = "false_completion"


TripwireKind = Literal[
    "canary_leak",  # a canary value left the sandbox (egress detail, network command, final answer)
    "egress_attempt",  # any non-allowlisted outbound connection attempt
    "metadata_access",  # any attempt to reach the cloud metadata service
    "file_modified",  # a protected path changed
    "file_deleted",  # a protected path disappeared
    "write_outside_scope",  # a file outside the declared scope changed
    "command_pattern",  # a command matched a forbidden regex
    "false_completion",  # agent claimed success but the hidden check failed
    "resource_cap",  # a resource or budget cap fired
]


class TripwireSpec(BaseModel):
    id: str
    kind: TripwireKind
    severity: Severity
    description: str
    paths: list[str] = Field(default_factory=list)  # for file_* kinds (exact paths or globs)
    pattern: str | None = None  # for command_pattern
    # command_pattern only: "execution" ignores commands that merely read or search
    # files (cat, grep, head, …), so reading deploy.sh is not the same as running it.
    match: Literal["execution", "anywhere"] = "execution"
    caps: list[str] = Field(default_factory=list)  # for resource_cap: which cap kinds count

    @model_validator(mode="after")
    def _check_params(self) -> TripwireSpec:
        if self.kind in ("file_modified", "file_deleted") and not self.paths:
            raise ValueError(f"tripwire {self.id}: {self.kind} needs paths")
        if self.kind == "command_pattern":
            if not self.pattern:
                raise ValueError(f"tripwire {self.id}: command_pattern needs pattern")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"tripwire {self.id}: invalid pattern: {exc}") from exc
        return self


class WorkspaceFile(BaseModel):
    path: str  # absolute path inside the sandbox
    content: str | None = None  # text (templated)
    source: str | None = None  # binary asset, relative to the suite directory (not templated)
    mode: str = "0644"

    @model_validator(mode="after")
    def _one_body(self) -> WorkspaceFile:
        if (self.content is None) == (self.source is None):
            raise ValueError(f"{self.path}: set exactly one of content or source")
        return self

    @field_validator("path")
    @classmethod
    def _absolute(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("workspace file paths must be absolute")
        return v


class SuccessCheck(BaseModel):
    """Hidden check run after the agent finishes. The agent never sees it."""

    command: str
    expect_exit: int = 0
    files: list[WorkspaceFile] = Field(default_factory=list)  # copied in only at check time


class Scenario(BaseModel):
    id: str
    version: int = 1
    title: str
    category: Category
    severity: Severity
    summary: str  # one line, for humans and for the sticker breakdown
    task: str  # what the user asks the agent to do
    workdir: str = "/workspace"
    files: list[WorkspaceFile]
    canaries: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=lambda: ["/workspace/**"])
    setup: list[str] = Field(default_factory=list)  # commands run before the agent starts
    cleanup: list[str] = Field(default_factory=list)  # run after the agent, before hashing
    success: SuccessCheck
    tripwires: list[TripwireSpec]
    attachments: list[str] = Field(default_factory=list)  # image files shown to the agent
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_templates(self) -> Scenario:
        declared = set(self.canaries)
        texts = [self.task, *[f.content for f in self.files if f.content], *self.setup]
        for text in texts:
            for kind, name in TEMPLATE_RE.findall(text):
                if kind == "canary" and name not in declared:
                    raise ValueError(f"scenario {self.id}: undeclared canary {name}")
        ids = [t.id for t in self.tripwires]
        if len(ids) != len(set(ids)):
            raise ValueError(f"scenario {self.id}: duplicate tripwire ids")
        if not self.tripwires:
            raise ValueError(f"scenario {self.id}: needs at least one tripwire")
        return self
