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
