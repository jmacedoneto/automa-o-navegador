export type AutomationMode = "gravado" | "hibrido" | "livre_ai";

export interface FallbackPolicy {
  maxTentativasIa: number;
  timeoutTotalSegundos: number;
  pausaQuandoFalhar: boolean;
}

export interface RecordingSession {
  id: string;
  automationId?: string;
  status: "pending" | "running" | "completed" | "failed";
  runtimeId?: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface ExecutionJob {
  id: string;
  automationId: string;
  triggerType: "manual" | "webhook" | "schedule";
  mode: AutomationMode;
  payload: Record<string, unknown>;
}

export interface ExecutionRun {
  id: string;
  jobId: string;
  status: "queued" | "running" | "paused" | "success" | "failed";
  stepsCompleted: number;
  totalSteps: number;
}
