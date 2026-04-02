export function buildExecutionJobRequest(automationId: string) {
  return {
    automation_id: automationId,
    trigger_type: "manual",
    mode: "hibrido",
    payload: {},
  };
}
