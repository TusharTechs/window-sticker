"""Map traps to the security standards buyers already use.

Every trap category maps to entries of the OWASP Top 10 for LLM Applications (2025 edition), so
a sticker can say which risks it measured in the language of a security review. The mapping is by
category, not per file, so it never changes a suite's digest.
"""

from __future__ import annotations

from typing import Any

OWASP_LLM_2025: dict[str, str] = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM03": "Supply Chain",
    "LLM04": "Data and Model Poisoning",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM07": "System Prompt Leakage",
    "LLM08": "Vector and Embedding Weaknesses",
    "LLM09": "Misinformation",
    "LLM10": "Unbounded Consumption",
}

CATEGORY_OWASP: dict[str, tuple[str, ...]] = {
    "prompt_injection_file": ("LLM01", "LLM06"),
    "prompt_injection_ticket": ("LLM01", "LLM06"),
    "prompt_injection_tool_output": ("LLM01", "LLM05", "LLM06"),
    "prompt_injection_image": ("LLM01", "LLM06"),
    "cloud_metadata": ("LLM02", "LLM06"),
    "credential_discovery": ("LLM02",),
    "destructive_shortcut": ("LLM06",),
    "scope_creep": ("LLM06",),
    "dependency_confusion": ("LLM03", "LLM06"),
    "dns_exfiltration": ("LLM02", "LLM06"),
    "resource_abuse": ("LLM10",),
    "false_completion": ("LLM09",),
}


def owasp_for(category: str) -> list[str]:
    return list(CATEGORY_OWASP.get(category, ()))


def coverage(breakdown: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per OWASP risk: how many traps and runs measured it, and how many incidents it found."""
    out: dict[str, dict[str, Any]] = {}
    for b in breakdown:
        for code in owasp_for(b["category"]):
            row = out.setdefault(
                code,
                {
                    "id": code,
                    "name": OWASP_LLM_2025[code],
                    "traps": 0,
                    "runs": 0,
                    "incidents": 0,
                    "serious": 0,
                },
            )
            row["traps"] += 1
            row["runs"] += b["runs"]
            row["incidents"] += b["incidents"]
            row["serious"] += b["serious"]
    return sorted(out.values(), key=lambda r: r["id"])
