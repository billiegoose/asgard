import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MARKER = "ultrapowers-pi routing bootstrap";

export default function ultrapowersPi(pi: ExtensionAPI) {
  pi.on("session_start", async () => ({}));
  pi.on("context", async (event) => {
    if (event.messages.some((m: any) => JSON.stringify(m.content ?? "").includes(MARKER))) return;
    const routing = process.env.PASEO_AGENT_ID?.trim()
      ? "This session is running in Paseo: for new orchestration, prefer Paseo-managed agents for implementation, planning proof readers, and reviews so the operator can inspect their tabs and errors. Read the paseo skill; use agent-scoped Paseo tools or the CLI at PASEO_CLI. Choose configured profiles or discovered compatible OpenAI models; a catalog listing is not proof a model can run. Preserve workspace isolation, evidence gates, visible agent IDs and completion notifications. Report Paseo failures; no silent Pi/Taskplane/CLI fallback."
      : "Outside Paseo, use Pi subagent workflows or Taskplane orchestration according to the local ultrapowers skill.";
    return {
      messages: [
        {
          role: "user" as const,
          content: [{ type: "text" as const, text: `<${MARKER}>\nUltrapowers is installed for this project. When Superpowers writing-plans is used for implementation planning, also use ultraplan. At execution handoff, use /skill:ultrapowers and read .pi/skills/ultrapowers/SKILL.md for this project's backend selection. ${routing} Explicit operator backend choices and capability/permission boundaries still apply. Keep existing runs on their current backend; this preference does not authorize migration, duplicate workers, or nested delegation. Do not use Claude-only Workflow/Task/Skill tools.\n</${MARKER}>` }],
          timestamp: Date.now(),
        },
        ...event.messages,
      ],
    };
  });
}
