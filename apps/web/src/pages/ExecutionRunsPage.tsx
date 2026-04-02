import { useSearchParams } from "react-router-dom";

import { buildExecutionJobRequest } from "../domains/executions/api";

export default function ExecutionRunsPage() {
  const [searchParams] = useSearchParams();
  const automationId = searchParams.get("automationId");
  const request = automationId ? buildExecutionJobRequest(automationId) : null;

  return (
    <section>
      <h1>Execution runs</h1>
      <p>Route shell for upcoming runtime job polling and status rendering.</p>
      <pre>{JSON.stringify(request, null, 2)}</pre>
    </section>
  );
}
