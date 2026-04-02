import { useParams } from "react-router-dom";

export default function AutomationEditorPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <section>
      <h1>Automation editor</h1>
      <p>Route shell for the new web app automation editor.</p>
      <pre>{JSON.stringify({ automationId: id ?? "new" }, null, 2)}</pre>
    </section>
  );
}
