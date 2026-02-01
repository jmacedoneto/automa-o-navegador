export interface AutomationStep {
  order: number;
  action: 'navigate' | 'click' | 'type' | 'wait' | 'waitForSelector' | 'screenshot' | 'extractTable';
  selector?: string;
  value?: string;
  description: string;
  waitTime?: number;
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
  created_at: string;
  updated_at: string;
}

export interface GenerateStepsResponse {
  steps: AutomationStep[];
  notes: string;
}
