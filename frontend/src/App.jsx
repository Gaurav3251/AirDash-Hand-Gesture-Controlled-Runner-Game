import { useEffect, useState, useCallback } from "react";
import { fetchSessions, fetchSessionSummary } from "./api.js";

const GESTURE_MAP = [
  ["Swipe left / right", "Change lane"],
  ["Slide up", "Jump (clears ground obstacles)"],
  ["Slide down", "Duck (clears overhead obstacles)"],
  ["Open palm (held)", "Pause / resume / restart"],
  ["Fist (held)", "Stop — ends the run immediately"],
  ["Thumbs up (held)", "+1 life (up to 3)"],
];

function StatCard({ label, value, ok }) {
  return (
    <div className={`card ${ok === undefined ? "" : ok ? "pass" : "fail"}`}>
      <div className="card-label">{label}</div>
      <div className="card-value">{value}</div>
    </div>
  );
}

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null); // null = latest
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(() => {
    fetchSessions()
      .then(setSessions)
      .catch((e) => setError(e.message));
  }, []);

  const loadSummary = useCallback((sessionId) => {
    setLoading(true);
    setError(null);
    fetchSessionSummary(sessionId)
      .then(setSummary)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSessions();
    loadSummary(null);
  }, [loadSessions, loadSummary]);

  const handleSelect = (id) => {
    setSelectedId(id);
    loadSummary(id);
  };

  const handleRefresh = () => {
    loadSessions();
    loadSummary(selectedId);
  };

  return (
    <main>
      <header>
        <h1>Gesture Gaming MVP Dashboard</h1>
        <p className="muted">
          Post-session evaluation data, read live from the FastAPI backend
          (<code>backend/api.py</code>). Play a session with{" "}
          <code>python main.py --input gesture</code>, then refresh here.
        </p>
        <button onClick={handleRefresh}>Refresh</button>
      </header>

      {error && (
        <section className="card fail" style={{ marginBottom: 24 }}>
          <strong>Couldn't reach the backend.</strong>
          <div className="muted">
            {error} — make sure it's running:{" "}
            <code>uvicorn backend.api:app --reload --port 8000</code>
          </div>
        </section>
      )}

      {!error && loading && <p className="muted">Loading…</p>}

      {!error && !loading && !summary && (
        <p className="muted">
          No sessions logged yet. Run <code>python main.py --input gesture</code>{" "}
          (or <code>--input keyboard</code>) to play one, then hit Refresh.
        </p>
      )}

      {!error && summary && !loading && (
        <>
          <h2>
            Session #{summary.session_id}{" "}
            <span className="muted">({summary.input_mode} mode)</span>
          </h2>
          <section className="grid">
            <StatCard label="Final score" value={summary.final_score} />
            <StatCard label="Completed" value={summary.completed ? "Yes" : "No"} />
            <StatCard
              label="Stable prediction rate"
              value={`${(summary.stable_prediction_rate * 100).toFixed(1)}%`}
              ok={summary.meets_accuracy_target}
            />
            <StatCard
              label="False triggers / min"
              value={summary.false_trigger_rate_per_min.toFixed(2)}
              ok={summary.meets_false_trigger_target}
            />
            <StatCard
              label="Avg latency"
              value={`${summary.avg_latency_ms.toFixed(0)}ms`}
              ok={summary.meets_latency_target}
            />
            <StatCard
              label="Avg FPS"
              value={summary.avg_fps.toFixed(1)}
              ok={summary.meets_fps_target}
            />
          </section>
        </>
      )}

      <section>
        <h2>All sessions</h2>
        {sessions.length === 0 ? (
          <p className="muted">No sessions logged yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Mode</th>
                <th>Completed</th>
                <th>Score</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className={s.id === selectedId ? "selected" : ""}>
                  <td>{s.id}</td>
                  <td>{s.input_mode}</td>
                  <td>{s.completed ? "Yes" : "No"}</td>
                  <td>{s.final_score}</td>
                  <td>
                    <button onClick={() => handleSelect(s.id)}>View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Gesture map</h2>
        <table>
          <tbody>
            {GESTURE_MAP.map(([gesture, action]) => (
              <tr key={gesture}>
                <th>{gesture}</th>
                <td>{action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
