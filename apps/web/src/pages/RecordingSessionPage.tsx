import { useParams } from "react-router-dom";

import { buildRecordingSessionRequest } from "../domains/recordings/api";

export default function RecordingSessionPage() {
  const { id } = useParams<{ id: string }>();
  const payload = buildRecordingSessionRequest(id);

  return (
    <section>
      <h1>Recording session</h1>
      <p>Ready to request an external Chrome recording session.</p>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}
