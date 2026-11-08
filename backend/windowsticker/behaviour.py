"""What an agent actually did on a given machine: the evidence behind an environment row.

Counts, across a test's stored runs, the moments where the machine shaped the agent's behaviour:
tools it reached for that were not installed, and how it went about getting packages. Each
signal keeps a few run ids so a reader can open the replay and see it happen.
"""

from __future__ import annotations

import re
from typing import Any

from windowsticker.grading.tripwires import executed_text, is_shell_command

TOOLS = ("git", "curl", "wget", "bash", "make", "gcc", "jq", "tomllib", "toml")
MISSING = {
    tool: re.compile(
        rf"(\b{tool}: (command )?not found|\b{tool}: No such file|No module named '?{tool}(?![\w.]))",
        re.IGNORECASE,
    )
    for tool in TOOLS
}
PACKAGE = {
    "installed a package": re.compile(r"(?<![\w-])(pip3?|-m\s+pip)\s+install(?![\w-])"),
    "downloaded a package": re.compile(r"(?<![\w-])(pip3?|-m\s+pip)\s+(download|wheel)(?![\w-])"),
    "named a non-default index": re.compile(r"--(extra-)?index-url|\s-i\s+https?://"),
}


def profile(records: list[dict[str, Any]], examples: int = 3) -> dict[str, Any]:
    """Summarise behaviour across stored run records (as returned by the runs API)."""
    missing: dict[str, dict[str, Any]] = {}
    package: dict[str, dict[str, Any]] = {}
    commands = 0
    for rec in records:
        run_id = rec.get("run_id", "")
        seen_missing: set[str] = set()
        seen_package: set[str] = set()
        for c in rec.get("evidence", {}).get("commands", []):
            cmd = c.get("command", "")
            if not is_shell_command(cmd) or c.get("blocked_by"):
                continue
            commands += 1
            out = f"{c.get('stdout', '')}\n{c.get('stderr', '')}"
            for tool, rx in MISSING.items():
                if rx.search(out):
                    seen_missing.add(tool)
            ran = executed_text(cmd)
            for label, rx in PACKAGE.items():
                if rx.search(ran):
                    seen_package.add(label)
        for tool in seen_missing:
            m = missing.setdefault(tool, {"runs": 0, "examples": []})
            m["runs"] += 1
            if len(m["examples"]) < examples:
                m["examples"].append(run_id)
        for label in seen_package:
            p = package.setdefault(label, {"runs": 0, "examples": []})
            p["runs"] += 1
            if len(p["examples"]) < examples:
                p["examples"].append(run_id)
    return {
        "runs": len(records),
        "commands": commands,
        "missing_tools": missing,
        "package_moves": package,
    }
