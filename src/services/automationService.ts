import { api } from "./api";
import { Automation, AutomationStep, Schedule, ExecutionLog, AutomationOutput } from "@/types/automation";

// ── Automations ────────────────────────────────────────────────────────────

export async function fetchAutomations(): Promise<Automation[]> {
  return api.get<Automation[]>("/automations");
}

export async function fetchAutomationById(id: string): Promise<Automation | null> {
  try {
    return await api.get<Automation>(`/automations/${id}`);
  } catch {
    return null;
  }
}

export async function createAutomation(
  data: Omit<Automation, "id" | "created_at" | "updated_at">
): Promise<Automation> {
  return api.post<Automation>("/automations", data);
}

export async function updateAutomation(
  id: string,
  data: Partial<Omit<Automation, "id" | "created_at" | "updated_at">>
): Promise<Automation> {
  return api.put<Automation>(`/automations/${id}`, data);
}

export async function deleteAutomation(id: string): Promise<void> {
  return api.delete(`/automations/${id}`);
}

export async function toggleAutomationStatus(id: string, isActive: boolean): Promise<void> {
  await api.put(`/automations/${id}`, { is_active: isActive });
}

export async function importSteps(id: string, steps: AutomationStep[]): Promise<{ imported: number }> {
  return api.post(`/automations/${id}/import-steps`, steps);
}

export async function cloneAutomation(id: string): Promise<Automation> {
  return api.post<Automation>(`/automations/${id}/clone`);
}

export async function parseSeleniumCsv(csv: string): Promise<{ steps: AutomationStep[]; count: number }> {
  return api.post("/automations/parse-selenium", { csv });
}

export async function importChromeRecording(recording: object): Promise<{ steps: AutomationStep[]; count: number }> {
  return api.post("/automations/import-chrome-recorder", { recording });
}

export async function runAiAgent(automationId: string, prompt: string): Promise<{ task_id: string; execution_id: string }> {
  return api.post(`/automations/${automationId}/run-agent`, { prompt });
}

export async function cancelExecution(logId: string): Promise<{ ok: boolean }> {
  return api.post(`/executions/${logId}/cancel`, {});
}

// ── Schedules ──────────────────────────────────────────────────────────────

export async function fetchAllSchedules(): Promise<Schedule[]> {
  return api.get<Schedule[]>("/schedules");
}

export async function fetchSchedulesByAutomation(automationId: string): Promise<Schedule[]> {
  return api.get<Schedule[]>(`/schedules?automation_id=${automationId}`);
}

export async function createSchedule(
  schedule: Omit<Schedule, "id" | "created_at">
): Promise<Schedule> {
  return api.post<Schedule>("/schedules", schedule);
}

export async function updateSchedule(id: string, data: Partial<Schedule>): Promise<Schedule> {
  return api.put<Schedule>(`/schedules/${id}`, data);
}

export async function toggleSchedule(id: string): Promise<{ is_active: boolean }> {
  return api.patch(`/schedules/${id}/toggle`);
}

export async function deleteSchedule(id: string): Promise<void> {
  return api.delete(`/schedules/${id}`);
}

// ── Execution logs ─────────────────────────────────────────────────────────

export async function fetchExecutionLogs(automationId?: string, limit = 50): Promise<ExecutionLog[]> {
  const qs = [
    automationId ? `automation_id=${automationId}` : "",
    `limit=${limit}`,
  ].filter(Boolean).join("&");
  return api.get<ExecutionLog[]>(`/executions?${qs}`);
}

export async function fetchExecutionLog(logId: string): Promise<ExecutionLog> {
  return api.get<ExecutionLog>(`/executions/${logId}`);
}

// ── AI ─────────────────────────────────────────────────────────────────────

export async function generateSteps(
  instructions: string,
  context?: string
): Promise<{ steps: AutomationStep[]; notes: string }> {
  const data = await api.post<{ steps: AutomationStep[] }>("/ai/generate-steps", {
    instructions,
    context: context || "",
  });
  return { steps: data.steps, notes: "" };
}

export async function fillVariables(
  placeholders: string[],
  contextData: Record<string, unknown>,
  instructions?: string
): Promise<Record<string, string>> {
  const data = await api.post<{ resolved: Record<string, string> }>("/ai/fill-variables", {
    placeholders,
    context_data: contextData,
    instructions: instructions || "",
  });
  return data.resolved;
}
