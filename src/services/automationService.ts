import { supabase } from "@/integrations/supabase/client";
import { Automation, AutomationStep, Schedule, ExecutionLog } from "@/types/automation";

// ============ AUTOMATIONS ============

export async function fetchAutomations(): Promise<Automation[]> {
  const { data, error } = await supabase
    .from('automations')
    .select('*')
    .order('created_at', { ascending: false });

  if (error) throw error;
  
  return (data || []).map(item => ({
    ...item,
    steps: (item.steps as unknown as AutomationStep[]) || [],
    credentials: item.credentials as Automation['credentials'],
    last_execution_status: item.last_execution_status as Automation['last_execution_status'],
  }));
}

export async function fetchAutomationById(id: string): Promise<Automation | null> {
  const { data, error } = await supabase
    .from('automations')
    .select('*')
    .eq('id', id)
    .single();

  if (error) {
    if (error.code === 'PGRST116') return null;
    throw error;
  }
  
  return {
    ...data,
    steps: (data.steps as unknown as AutomationStep[]) || [],
    credentials: data.credentials as Automation['credentials'],
    last_execution_status: data.last_execution_status as Automation['last_execution_status'],
  };
}

export async function createAutomation(automation: Omit<Automation, 'id' | 'created_at' | 'updated_at'>): Promise<Automation> {
  const { data, error } = await supabase
    .from('automations')
    .insert([{
      name: automation.name,
      description: automation.description,
      erp_url: automation.erp_url,
      browserless_url: automation.browserless_url,
      sheets_url: automation.sheets_url,
      instructions: automation.instructions,
      steps: JSON.parse(JSON.stringify(automation.steps)),
      is_active: automation.is_active,
      webhook_url: automation.webhook_url,
      webhook_secret: automation.webhook_secret,
      credentials: automation.credentials,
    }])
    .select()
    .single();

  if (error) throw error;
  
  return {
    ...data,
    steps: (data.steps as unknown as AutomationStep[]) || [],
    credentials: data.credentials as Automation['credentials'],
    last_execution_status: data.last_execution_status as Automation['last_execution_status'],
  };
}

export async function updateAutomation(id: string, updates: Partial<Automation>): Promise<Automation> {
  const updateData: Record<string, unknown> = {};
  
  if (updates.name !== undefined) updateData.name = updates.name;
  if (updates.description !== undefined) updateData.description = updates.description;
  if (updates.erp_url !== undefined) updateData.erp_url = updates.erp_url;
  if (updates.browserless_url !== undefined) updateData.browserless_url = updates.browserless_url;
  if (updates.sheets_url !== undefined) updateData.sheets_url = updates.sheets_url;
  if (updates.instructions !== undefined) updateData.instructions = updates.instructions;
  if (updates.steps !== undefined) updateData.steps = JSON.parse(JSON.stringify(updates.steps));
  if (updates.is_active !== undefined) updateData.is_active = updates.is_active;
  if (updates.webhook_url !== undefined) updateData.webhook_url = updates.webhook_url;
  if (updates.webhook_secret !== undefined) updateData.webhook_secret = updates.webhook_secret;
  if (updates.credentials !== undefined) updateData.credentials = updates.credentials;

  const { data, error } = await supabase
    .from('automations')
    .update(updateData)
    .eq('id', id)
    .select()
    .single();

  if (error) throw error;
  
  return {
    ...data,
    steps: (data.steps as unknown as AutomationStep[]) || [],
    credentials: data.credentials as Automation['credentials'],
    last_execution_status: data.last_execution_status as Automation['last_execution_status'],
  };
}

export async function deleteAutomation(id: string): Promise<void> {
  const { error } = await supabase
    .from('automations')
    .delete()
    .eq('id', id);

  if (error) throw error;
}

export async function toggleAutomationStatus(id: string, isActive: boolean): Promise<void> {
  const { error } = await supabase
    .from('automations')
    .update({ is_active: isActive })
    .eq('id', id);

  if (error) throw error;
}

// ============ SCHEDULES ============

export async function fetchSchedulesByAutomation(automationId: string): Promise<Schedule[]> {
  const { data, error } = await supabase
    .from('schedules')
    .select('*')
    .eq('automation_id', automationId)
    .order('created_at', { ascending: false });

  if (error) throw error;
  
  return (data || []).map(item => ({
    ...item,
    schedule_type: item.schedule_type as Schedule['schedule_type'],
  }));
}

export async function createSchedule(schedule: Omit<Schedule, 'id' | 'created_at' | 'updated_at'>): Promise<Schedule> {
  const { data, error } = await supabase
    .from('schedules')
    .insert([schedule])
    .select()
    .single();

  if (error) throw error;
  
  return {
    ...data,
    schedule_type: data.schedule_type as Schedule['schedule_type'],
  };
}

export async function deleteSchedule(id: string): Promise<void> {
  const { error } = await supabase
    .from('schedules')
    .delete()
    .eq('id', id);

  if (error) throw error;
}

// ============ EXECUTION LOGS ============

export async function fetchExecutionLogs(automationId: string, limit = 20): Promise<ExecutionLog[]> {
  const { data, error } = await supabase
    .from('execution_logs')
    .select('*')
    .eq('automation_id', automationId)
    .order('started_at', { ascending: false })
    .limit(limit);

  if (error) throw error;
  
  return (data || []).map(item => ({
    ...item,
    status: item.status as ExecutionLog['status'],
    screenshots: (item.screenshots as string[]) || [],
    extracted_data: (item.extracted_data as Record<string, unknown>) || {},
    webhook_response: item.webhook_response as Record<string, unknown> | undefined,
  }));
}

// ============ GENERATE STEPS ============

export async function generateSteps(instructions: string, erpUrl?: string): Promise<{ steps: AutomationStep[]; notes: string }> {
  const { data, error } = await supabase.functions.invoke('generate-steps', {
    body: { instructions, erpUrl }
  });

  if (error) throw error;
  if (data.error) throw new Error(data.error);

  return {
    steps: data.steps || [],
    notes: data.notes || "",
  };
}
