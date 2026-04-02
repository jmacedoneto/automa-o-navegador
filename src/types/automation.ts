import type { AutomationMode, FallbackPolicy } from "@autopilot/shared";

export interface AutomationStep {
  order: number;
  type?: string;  // FastAPI uses 'type'
  action?: string; // Legacy extension uses 'action'
  selector?: string;
  url?: string;
  value?: string;
  description?: string;
  waitTime?: number;
  duration?: number;
  key?: string;
  full_page?: boolean;
}

export type ScheduleType = 'once' | 'daily' | 'weekly' | 'monthly' | 'interval' | 'cron';
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
export type MediaType = 'image' | 'audio' | 'video';

// ── Output configs ─────────────────────────────────────────────────────────

export interface WebhookOutput {
  type: 'webhook';
  url: string;
  method?: string;
  headers?: Record<string, string>;
}

export interface WhatsAppOutput {
  type: 'whatsapp';
  provider?: 'evolution';
  api_url: string;
  api_key: string;
  instance: string;
  to: string;
  message?: string;
}

export interface SheetsOutput {
  type: 'sheets';
  spreadsheet_id: string;
  sheet?: string;
}

export type AutomationOutput = WebhookOutput | WhatsAppOutput | SheetsOutput;

// ── Main types ─────────────────────────────────────────────────────────────

export interface Schedule {
  id: string;
  automation_id: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  interval_minutes?: number;
  days_of_week?: number[];
  time_of_day?: string;
  timezone: string;
  is_active: boolean;
  next_run_at?: string;
  last_run_at?: string;
  created_at: string;
}

export interface ExecutionLog {
  id: string;
  automation_id: string;
  schedule_id?: string;
  started_at: string;
  finished_at?: string;
  status: ExecutionStatus;
  error_message?: string;
  steps_completed: number;
  total_steps: number;
  screenshots: string[];
  extracted_data: Record<string, unknown>;
}

export interface MediaUpload {
  id: string;
  automation_id?: string;
  file_type: MediaType;
  file_url: string;
  file_name?: string;
  file_size?: number;
  created_at: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string;
  erp_url: string;
  instructions: string;
  mode: AutomationMode;
  fallback_policy: FallbackPolicy;
  steps: AutomationStep[];
  is_active: boolean;
  credentials?: Record<string, string>;
  outputs: AutomationOutput[];
  last_execution_at?: string;
  last_execution_status?: ExecutionStatus;
  created_at: string;
  updated_at: string;
}

export interface GenerateStepsResponse {
  steps: AutomationStep[];
  notes: string;
}

export interface ExecutionSession {
  executionId: string;
  task_id?: string;
  status: 'starting' | 'running' | 'completed' | 'success' | 'failed' | 'queued';
  currentStep: number;
  totalSteps: number;
  latestScreenshot?: string;
}
