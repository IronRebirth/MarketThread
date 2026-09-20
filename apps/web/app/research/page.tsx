import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredGate } from "../../components/auth/auth-required-gate";
import { ResearchAssistantWorkspace } from "../../components/research/research-assistant-workspace";

export default function ResearchPage() {
  return (
    <AppShell>
      <AuthRequiredGate nextPath="/research">
        <ResearchAssistantWorkspace />
      </AuthRequiredGate>
    </AppShell>
  );
}
