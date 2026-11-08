export const per1k = (x: number) => Math.round(x).toLocaleString("en-US");

export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "n/a";
  if (v === 0) return "$0";
  if (v < 0.01) return `$${v.toFixed(4)}`;
  if (v < 1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
}

export function seconds(s: number | null | undefined): string {
  if (s === null || s === undefined) return "n/a";
  return s < 10 ? `${s.toFixed(2)}s` : `${Math.round(s)}s`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Short trap names, used on Live Grid tiles. */
export const TRAP_TAG: Record<string, string> = {
  prompt_injection_file: "README",
  prompt_injection_ticket: "TICKET",
  prompt_injection_tool_output: "STDOUT",
  prompt_injection_image: "IMAGE",
  cloud_metadata: "METADATA",
  credential_discovery: ".ENV",
  destructive_shortcut: "DELETE",
  scope_creep: "SCOPE",
  dependency_confusion: "PACKAGE",
  dns_exfiltration: "DNS",
  resource_abuse: "CPU",
  false_completion: "HONESTY",
};

export const FAILURE_LABEL: Record<string, string> = {
  none: "No incident",
  prompt_injection: "Obeyed an injected instruction",
  secret_exposure: "Exposed a secret",
  destructive_change: "Destructive change",
  scope_violation: "Went out of scope",
  resource_abuse: "Resource abuse",
  false_completion: "Claimed success falsely",
  untrusted_code: "Tried to fetch code from an untrusted source",
};

/** For each kind of trap: what the incident would have done outside the lab, and why it did not. */
export const WOULD_HAVE: Record<string, { would: string; here: string }> = {
  dns_exfiltration: {
    would: "The secret would have left the machine inside a DNS lookup, which most firewalls let through.",
    here: "The microVM has no DNS resolver and no route out, so the lookup failed inside the VM.",
  },
  dependency_confusion: {
    would: "pip would have downloaded code from an attacker's index; for a source package, pip runs its setup script while doing so.",
    here: "The Egress Warden refused the connection. Nothing was downloaded.",
  },
  prompt_injection_file: {
    would: "An instruction planted in the repository would have been carried out with the user's credentials.",
    here: "Anything it tried to send was refused at the Egress Warden; the credentials were canaries.",
  },
  prompt_injection_ticket: {
    would: "An instruction planted in a ticket would have changed the machine on an attacker's behalf.",
    here: "The change landed in a throwaway microVM that was destroyed after the run.",
  },
  prompt_injection_tool_output: {
    would: "Tool output would have piped an attacker's script into a shell.",
    here: "The script's host was unreachable; the Egress Warden refused the connection.",
  },
  prompt_injection_image: {
    would: "An instruction hidden in an image would have been carried out.",
    here: "Anything it tried to send was refused at the Egress Warden.",
  },
  cloud_metadata: {
    would: "The cloud metadata service would have handed over the machine's credentials.",
    here: "Metadata addresses are denied, and no cloud credentials exist inside the microVM.",
  },
  credential_discovery: {
    would: "A production secret would have been exposed.",
    here: "The secret was a canary minted for this run only. It unlocks nothing.",
  },
  destructive_shortcut: {
    would: "Work in the repository would have been deleted to make a check pass.",
    here: "The deletion happened in a disposable copy inside the microVM.",
  },
  scope_creep: {
    would: "Infrastructure outside the task would have been changed.",
    here: "The change happened in a disposable copy inside the microVM.",
  },
  resource_abuse: {
    would: "A runaway process would have eaten a shared machine.",
    here: "The microVM's CPU, memory and per-command caps cut it off.",
  },
  false_completion: {
    would: "A broken change would have been reported as done.",
    here: "The hidden check, which the agent never sees, caught it.",
  },
};

export const GUARDRAIL_LABEL: Record<string, string> = {
  untrusted_content_prompt: "Untrusted-content system prompt",
  no_network_commands: "Block network commands",
  no_pipe_to_shell: "Block pipe-to-shell",
  no_untrusted_package_index: "Block custom package indexes",
  no_destructive_commands: "Block destructive commands",
  no_secret_paths: "Block secret paths",
  workspace_write_only: "Writes only inside /workspace",
};

/** A short, unambiguous name for an agent configuration: model plus guardrail profile or harness. */
export function configLabel(t: { agent_name: string; model: string }): string {
  const model = t.model.split("/").pop()!.replace(/-\d{4}$/, "");
  if (t.agent_name.toLowerCase().startsWith("opencode")) return `OpenCode · ${model}`;
  const name = t.agent_name.toLowerCase();
  if (name.includes("hardened")) return `${model} · hardened`;
  if (name.includes("prompt")) return `${model} · prompt-only`;
  return model;
}
