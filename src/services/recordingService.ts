import { supabase } from "@/integrations/supabase/client";
import { AutomationStep } from "@/types/automation";

export interface CapturedAction {
  type: 'click' | 'type' | 'navigate' | 'scroll';
  timestamp: number;
  selector?: string;
  value?: string;
  url?: string;
  description?: string;
  x?: number;
  y?: number;
}

export interface RecordingSession {
  sessionId: string;
  liveUrl: string;
  wsEndpoint: string;
  erpUrl: string;
  initialScreenshot?: string;
  pageInfo?: {
    url: string;
    title: string;
  };
}

export interface StopRecordingResult {
  success: boolean;
  steps: AutomationStep[];
  notes?: string;
  screenshot?: string;
  pageUrl?: string;
  pageTitle?: string;
  error?: string;
}

/**
 * Start a new recording session
 */
export async function startRecordingSession(erpUrl: string): Promise<RecordingSession> {
  console.log('[recordingService] Starting recording session for:', erpUrl);

  const { data, error } = await supabase.functions.invoke('start-recording-session', {
    body: { erpUrl },
  });

  if (error) {
    console.error('[recordingService] Failed to start recording:', error);
    throw new Error(error.message || 'Erro ao iniciar gravação');
  }

  if (!data.success) {
    throw new Error(data.error || 'Erro ao iniciar sessão de gravação');
  }

  console.log('[recordingService] Session started:', data.sessionId);
  
  return {
    sessionId: data.sessionId,
    liveUrl: data.liveUrl,
    wsEndpoint: data.wsEndpoint,
    erpUrl: data.erpUrl,
    initialScreenshot: data.initialScreenshot,
    pageInfo: data.pageInfo,
  };
}

/**
 * Stop a recording session and generate automation steps
 */
export async function stopRecordingSession(
  sessionId: string,
  erpUrl: string,
  capturedActions: CapturedAction[]
): Promise<StopRecordingResult> {
  console.log('[recordingService] Stopping recording session:', sessionId);
  console.log('[recordingService] Captured actions:', capturedActions.length);

  const { data, error } = await supabase.functions.invoke('stop-recording-session', {
    body: {
      sessionId,
      erpUrl,
      capturedActions,
    },
  });

  if (error) {
    console.error('[recordingService] Failed to stop recording:', error);
    throw new Error(error.message || 'Erro ao parar gravação');
  }

  if (!data.success && data.error) {
    throw new Error(data.error);
  }

  console.log('[recordingService] Steps generated:', data.steps?.length || 0);

  return {
    success: data.success,
    steps: data.steps || [],
    notes: data.notes,
    screenshot: data.screenshot,
    pageUrl: data.pageUrl,
    pageTitle: data.pageTitle,
  };
}

/**
 * Add a captured action during recording
 */
export function createCapturedAction(
  type: CapturedAction['type'],
  details: Partial<CapturedAction>
): CapturedAction {
  return {
    type,
    timestamp: Date.now(),
    ...details,
  };
}
