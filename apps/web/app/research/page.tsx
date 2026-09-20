import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredPrompt } from "../../components/auth/auth-required-prompt";
import { useAuth } from "../../components/auth/auth-provider";
import { ResearchAssistantWorkspace } from "../../components/research/research-assistant-workspace";

export default function ResearchPage() {
  return (
    <AppShell>
      <ResearchAssistantWorkspace />
    </AppShell>
  );
}
