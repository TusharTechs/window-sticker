"""The machines an agent can be crash-tested on.

The same agent and the same traps, on different operating systems and toolchains. Agents
improvise when the tools they expect are missing (no curl, no bash, no stdlib TOML parser),
so a safety rating measured on one machine does not automatically hold on another. Each
environment is an OCI image the microVM boots; every one ships Python, which the traps and
the harness's own file snapshot need.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Environment:
    id: str
    image: str
    title: str
    os: str
    notes: str


ENVIRONMENTS: dict[str, Environment] = {
    e.id: e
    for e in (
        Environment(
            "debian",
            "python:3.12",
            "Debian 12, full toolchain",
            "Debian 12 (bookworm) · Python 3.12 · bash",
            "The baseline: bash, curl, wget, git and a compiler are all there.",
        ),
        Environment(
            "debian-slim",
            "python:3.12-slim",
            "Debian 12, slim",
            "Debian 12 (bookworm) · Python 3.12 · bash",
            "A typical production container: no curl, no wget, no git.",
        ),
        Environment(
            "alpine",
            "python:3.12-alpine",
            "Alpine Linux",
            "Alpine 3 · Python 3.12 · BusyBox ash, musl libc",
            "No bash and BusyBox versions of the usual tools; wget instead of curl.",
        ),
        Environment(
            "debian11-py310",
            "python:3.10-slim-bullseye",
            "Debian 11, Python 3.10",
            "Debian 11 (bullseye) · Python 3.10 · bash",
            "An older stack: no built-in TOML parser, so a task may tempt the agent to install one.",
        ),
    )
}
DEFAULT_ENVIRONMENT = "debian"


def get_environment(env_id: str) -> Environment:
    try:
        return ENVIRONMENTS[env_id]
    except KeyError:
        raise KeyError(
            f"unknown environment {env_id!r}; known: {', '.join(ENVIRONMENTS)}"
        ) from None
