export interface AutomationStep {
  order: number;
  action: 'navigate' | 'click' | 'type' | 'wait' | 'waitForSelector' | 'screenshot' | 'extractTable';
  selector?: string;
  value?: string;
  description: string;
  waitTime?: number;
}

export type ScheduleType = 'once' | 'daily' | 'weekly' | 'monthly' | 'interval';
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
export type MediaType = 'image' | 'audio' | 'video';

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
  updated_at: string;
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
  webhook_response?: Record<string, unknown>;
  created_at: string;
}

export interface MediaUpload {
  id: string;
  automation_id?: string;
  file_type: MediaType;
  file_url: string;
  file_name?: string;
  file_size?: number;
  transcription?: string;
  analysis?: Record<string, unknown>;
  created_at: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string | null;
  erp_url: string;
  browserless_url: string;
  sheets_url: string;
  instructions: string;
  steps: AutomationStep[];
  is_active: boolean;
  webhook_url?: string;
  webhook_secret?: string;
  credentials?: {
    username?: string;
    password?: string;
  };
  last_execution_at?: string;
  last_execution_status?: ExecutionStatus;
  created_at: string;
  updated_at: string;
  // Relations
  schedules?: Schedule[];
  execution_logs?: ExecutionLog[];
}

export interface GenerateStepsResponse {
  steps: AutomationStep[];
  notes: string;
}

export interface ExecutionSession {
  executionId: string;
  liveUrl?: string;
  status: 'starting' | 'running' | 'completed' | 'success' | 'failed';
  currentStep: number;
  totalSteps: number;
}
