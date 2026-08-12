import { api } from "./api";
import { ExecutionSession, ExecutionLog } from "@/types/automation";
import { supabase } from "@/integrations/supabase/client";

export interface ExecuteResult {
  success: boolean;
  task_id?: string;
  executionId?: string;
  liveUrl?: string;
  error?: string;
}

export async function executeAutomation(
  automationId: string,
  variables: Record<string, unknown> = {}
): Promise<ExecuteResult> {
  try {
    const data = await api.post<{ task_id: string; status: string; execution_id?: string; liveUrl?: string }>(
      `/automations/${automationId}/execute`,
      variables
    );
    return {
      success: true,
      task_id: data.task_id,
      executionId: data.execution_id,
      liveUrl: data.liveUrl,
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Erro desconhecido",
    };
  }
}

const FINAL_STATUSES = new Set(["success", "completed", "failed"]);

export async function getExecutionStatus(logId: string): Promise<ExecutionSession | null> {
  try {
    const log = await api.get<ExecutionLog>(`/executions/${logId}`);
    return {
      executionId: log.id,
      status: log.status as ExecutionSession["status"],
      currentStep: log.steps_completed || 0,
      totalSteps: log.total_steps || 0,
      latestScreenshot: log.screenshots?.length ? log.screenshots[log.screenshots.length - 1] : undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Poll the FastAPI backend every 2s until the execution reaches a final state.
 * Falls back to Supabase Realtime as a bonus if it happens to work.
 */
export function subscribeToExecution(
  executionId: string,
  onUpdate: (session: ExecutionSession) => void
): () => void {
  let stopped = false;

  const poll = async () => {
    while (!stopped) {
      await new Promise(r => setTimeout(r, 2000));
      if (stopped) break;
      const status = await getExecutionStatus(executionId);
      if (!status) continue;
      onUpdate(status);
      if (FINAL_STATUSES.has(status.status)) break;
    }
  };

  poll();

  // Also try Supabase Realtime as a bonus (instant updates when it works)
  const channel = supabase
    .channel(`execution-${executionId}`)
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "execution_logs", filter: `id=eq.${executionId}` },
      (payload) => {
        const data = payload.new as Record<string, unknown>;
        onUpdate({
          executionId: data.id as string,
          status: data.status as ExecutionSession["status"],
          currentStep: (data.steps_completed as number) || 0,
          totalSteps: (data.total_steps as number) || 0,
          latestScreenshot: (() => { const s = data.screenshots as string[] | undefined; return s?.length ? s[s.length - 1] : undefined; })(),
        });
      }
    )
    .subscribe();

  return () => {
    stopped = true;
    supabase.removeChannel(channel);
  };
}
