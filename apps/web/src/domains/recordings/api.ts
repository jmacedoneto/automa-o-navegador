export function buildRecordingSessionRequest(automationId?: string) {
  return {
    automation_id: automationId ?? null,
  };
}
