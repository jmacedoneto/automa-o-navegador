import { supabase } from "@/integrations/supabase/client";
import { ExecutionSession } from "@/types/automation";

export interface ExecuteOptions {
  withLivePreview?: boolean;
}

export interface ExecuteResult {
  success: boolean;
  executionId?: string;
  liveUrl?: string;
  totalSteps?: number;
  stepsCompleted?: number;
  extractedData?: Record<string, unknown>;
  screenshots?: string[];
  error?: string;
}

export async function executeAutomation(
  automationId: string, 
  options: ExecuteOptions = {}
): Promise<ExecuteResult> {
  try {
    const { data, error } = await supabase.functions.invoke('execute-automation', {
      body: {
        automationId,
        withLivePreview: options.withLivePreview || false,
      },
    });

    if (error) {
      console.error('[executionService] Edge function error:', error);
      return {
        success: false,
        error: error.message,
      };
    }

    return {
      success: data.success,
      executionId: data.executionId,
      liveUrl: data.liveUrl,
      totalSteps: data.totalSteps,
      stepsCompleted: data.stepsCompleted,
      extractedData: data.extractedData,
      screenshots: data.screenshots,
      error: data.error,
    };
  } catch (error) {
    console.error('[executionService] Unexpected error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Erro desconhecido',
    };
  }
}

export async function getExecutionStatus(executionId: string): Promise<ExecutionSession | null> {
  try {
    const { data, error } = await supabase
      .from('execution_logs')
      .select('*')
      .eq('id', executionId)
      .single();

    if (error || !data) {
      console.error('[executionService] Failed to get execution status:', error);
      return null;
    }

    return {
      executionId: data.id,
      status: data.status as ExecutionSession['status'],
      currentStep: data.steps_completed || 0,
      totalSteps: data.total_steps || 0,
    };
  } catch (error) {
    console.error('[executionService] Error fetching execution status:', error);
    return null;
  }
}

export function subscribeToExecution(
  executionId: string,
  onUpdate: (session: ExecutionSession) => void
): () => void {
  const channel = supabase
    .channel(`execution-${executionId}`)
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'execution_logs',
        filter: `id=eq.${executionId}`,
      },
      (payload) => {
        const data = payload.new as any;
        onUpdate({
          executionId: data.id,
          status: data.status,
          currentStep: data.steps_completed || 0,
          totalSteps: data.total_steps || 0,
        });
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
