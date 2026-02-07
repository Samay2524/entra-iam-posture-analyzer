import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../api";
import { storage } from "../storage";

export default function IdentityDetail() {
  const [searchParams] = useSearchParams();
  const [identities, setIdentities] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [details, setDetails] = useState(null);
  const [aiPacket, setAiPacket] = useState(null);
  const [message, setMessage] = useState(null);
  const [identityTasks, setIdentityTasks] = useState([]);
  const [ticketPreview, setTicketPreview] = useState(null);
  const [showRawTicket, setShowRawTicket] = useState(false);
  const identityParam = searchParams.get("identityId");

  const LAST_IDENTITY_KEY = "iam.identity.lastSelected";
  const [autoProcessedForId, setAutoProcessedForId] = useState("");
  const [autoTaskId, setAutoTaskId] = useState("");
  const [autoCreatedForId, setAutoCreatedForId] = useState("");

  useEffect(() => {
    apiGet("/identities").then(setIdentities).catch(() => setIdentities([]));
  }, []);

  useEffect(() => {
    const stored = storage.readJson(LAST_IDENTITY_KEY, null);
    const nextId = identityParam || stored?.id || "";
    if (nextId && nextId !== selectedId) {
      setSelectedId(String(nextId));
    }
  }, [identityParam, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    apiGet(`/identities/${selectedId}`).then(setDetails).catch(() => setDetails(null));
    storage.writeJson(LAST_IDENTITY_KEY, { id: String(selectedId) });
    setTicketPreview(null);
    setShowRawTicket(false);
    setAiPacket(null);
    setAutoCreatedForId("");
    setAutoProcessedForId("");
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    apiGet("/tasks", { identity_id: selectedId })
      .then(setIdentityTasks)
      .catch(() => setIdentityTasks([]));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    if (identityTasks.length > 0) return;
    if (autoCreatedForId === String(selectedId)) return;
    setAutoCreatedForId(String(selectedId));
    saveTask({
      identity_id: Number(selectedId),
      task_type: "ACCESS_REVIEW",
      priority: "P2",
      status: "OPEN",
      assignee: null,
    }).then((result) => {
      if (result?.task_id) {
        setAutoTaskId(String(result.task_id));
        autoGenerateReport(String(result.task_id));
      }
    });
  }, [selectedId, identityTasks, autoCreatedForId]);

  useEffect(() => {
    if (!selectedId) return;
    if (!latestTaskId) return;
    autoGenerateReport(latestTaskId);
  }, [selectedId, latestTaskId]);

  const handle = async (fn) => {
    setMessage(null);
    try {
      const result = await fn();
      setMessage({ type: "success", text: "Saved." });
      return result;
    } catch (err) {
      setMessage({ type: "error", text: err.message });
      return null;
    }
  };

  const refreshTasks = async () => {
    if (!selectedId) return [];
    try {
      const result = await apiGet("/tasks", { identity_id: selectedId });
      setIdentityTasks(result);
      return result;
    } catch {
      setIdentityTasks([]);
      return [];
    }
  };

  const saveTask = async (payload) => {
    const result = await handle(() => apiPost("/tasks", payload));
    if (result) {
      await refreshTasks();
    }
    return result;
  };

  const autoGenerateReport = async (taskId) => {
    if (!taskId || !selectedId) return;
    if (autoProcessedForId === String(selectedId)) return;
    setAutoProcessedForId(String(selectedId));
    const ai = await handle(() => apiPost(`/ai/${selectedId}`));
    if (ai?.packet) setAiPacket(ai.packet);
    const exported = await handle(() => apiPost(`/export/ticket/${taskId}`));
    if (exported) {
      const preview = await handle(() => apiGet(`/export/ticket/${taskId}/preview`));
      if (preview?.payload) setTicketPreview(preview.payload);
      setMessage({
        type: "success",
        text: "AI report generated and exported to Reports → Exports.",
      });
    }
  };

  const findingCount = useMemo(() => (details?.findings || []).length, [details]);
  const roleCount = useMemo(() => (details?.roles || []).length, [details]);
  const ownerCount = useMemo(() => (details?.owners || []).length, [details]);
  const credCount = useMemo(() => (details?.credentials || []).length, [details]);
  const latestTaskId = useMemo(() => {
    if (!identityTasks.length) return "";
    const sorted = [...identityTasks].sort((a, b) => {
      const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
      const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
      return bTime - aTime;
    });
    return String(sorted[0].id);
  }, [identityTasks]);

  useEffect(() => {
    if (!latestTaskId) {
      setAutoTaskId("");
      return;
    }
    setAutoTaskId(latestTaskId);
  }, [latestTaskId]);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="text-2xl font-semibold">Identity Review</div>
        <div className="text-sm text-muted mt-1">
          Pick an identity to review: Overview → Findings → AI Summary → Ticket.
        </div>
      </div>

      <div className="card p-6">
        <div className="text-sm text-muted mb-2">Select identity</div>
        <select
          className="border border-border rounded-lg px-3 py-2 w-full"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
        >
          <option value="">Choose an identity</option>
          {identities.map((i) => (
            <option key={i.id} value={i.id}>
              {i.display_name} ({i.id})
            </option>
          ))}
        </select>
      </div>

      {details && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="text-xs uppercase tracking-wide text-muted">Name</div>
              <div className="text-lg font-semibold">{details.display_name}</div>
              <div className="text-xs text-muted mt-1">{details.upn || "No sign-in name"}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs uppercase tracking-wide text-muted">Type</div>
              <div className="text-lg font-semibold">{details.type}</div>
              <div className="text-xs text-muted mt-1">
                {details.account_enabled === false ? "Disabled" : "Enabled"}
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs uppercase tracking-wide text-muted">Findings</div>
              <div className="text-lg font-semibold">{findingCount}</div>
              <div className="text-xs text-muted mt-1">Issues detected</div>
            </div>
            <div className="card p-4">
              <div className="text-xs uppercase tracking-wide text-muted">Roles</div>
              <div className="text-lg font-semibold">{roleCount}</div>
              <div className="text-xs text-muted mt-1">Assigned roles</div>
            </div>
          </div>

          <div className="card p-6 space-y-4">
            <div className="text-lg font-semibold">Overview</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-muted">Last sign-in</div>
                <div>{details.last_signin_at || "No data"}</div>
              </div>
              <div>
                <div className="text-muted">Owners</div>
                <div>{ownerCount}</div>
              </div>
              <div>
                <div className="text-muted">Credentials</div>
                <div>{credCount}</div>
              </div>
            </div>
          </div>

          <div className="card p-6 space-y-3">
            <div className="text-lg font-semibold">Findings</div>
            <div className="text-sm text-muted">
              These are the issues detected for this identity.
            </div>
            <div className="space-y-3">
              {(details.findings || []).map((f, idx) => (
                <div key={`${f.code}-${idx}`} className="border border-border rounded-lg p-3">
                  <div className="font-semibold">{f.title}</div>
                  <div className="text-xs text-muted">Severity: {f.severity}</div>
                  <div className="text-xs text-muted mt-1">
                    Evidence: {JSON.stringify(f.evidence || f.evidence_json || {})}
                  </div>
                </div>
              ))}
              {!details.findings?.length && (
                <div className="text-sm text-muted">No findings for this identity.</div>
              )}
            </div>
          </div>

          <div className="card p-6 space-y-4">
            <div className="text-lg font-semibold">AI Summary</div>
            <div className="text-sm text-muted">
              Generated automatically when you select an identity.
            </div>
            {aiPacket ? (
              <div className="border border-border rounded-lg p-5 space-y-4 text-base leading-relaxed">
                <div>
                  <div className="text-xs text-muted uppercase tracking-wide">Summary</div>
                  <div className="font-medium">{aiPacket.summary}</div>
                </div>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wide">Top risks</div>
                  <ul className="list-disc pl-5">
                    {(aiPacket.top_risks || []).map((risk, idx) => (
                      <li key={`${risk}-${idx}`}>{risk}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wide">Recommendation</div>
                  <div className="font-medium">{aiPacket.recommendation}</div>
                </div>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wide">Recommended actions</div>
                  <div className="space-y-2">
                    {(aiPacket.recommended_actions || []).map((action, idx) => (
                      <div key={`${action.action}-${idx}`} className="border border-border rounded-lg p-2">
                        <div className="font-medium">{action.action}</div>
                        <div className="text-sm text-muted">Why: {action.why}</div>
                        <div className="text-sm text-muted">Evidence: {action.evidence}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted uppercase tracking-wide">Ticket draft</div>
                  <div className="border border-border rounded-lg p-2">
                    <div className="font-medium">{aiPacket.ticket_draft?.title}</div>
                    <div className="text-sm text-muted mt-1">
                      {aiPacket.ticket_draft?.description}
                    </div>
                    <ul className="list-disc pl-5 text-sm text-muted mt-2">
                      {(aiPacket.ticket_draft?.acceptance_criteria || []).map((item, idx) => (
                        <li key={`${item}-${idx}`}>{item}</li>
                      ))}
                    </ul>
                    {aiPacket.ticket_draft?.risk_statement && (
                      <div className="text-sm text-muted mt-2">
                        Risk: {aiPacket.ticket_draft?.risk_statement}
                      </div>
                    )}
                  </div>
                </div>
                {aiPacket.questions_for_reviewer?.length ? (
                  <div>
                    <div className="text-xs text-muted">Questions for reviewer</div>
                    <ul className="list-disc pl-5">
                      {aiPacket.questions_for_reviewer.map((q, idx) => (
                        <li key={`${q}-${idx}`}>{q}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-muted">Generating AI summary…</div>
            )}
          </div>

          <div className="card p-6 space-y-4">
            <div className="text-lg font-semibold">Auto-generated Ticket</div>
            <div className="text-sm text-muted">
              Created automatically from the AI summary and saved to Reports → Exports.
            </div>
            {ticketPreview ? (
              <div className="border border-border rounded-lg p-4 space-y-3 text-sm">
                <div className="text-xs text-muted uppercase tracking-wide">Ticket preview</div>
                <div>
                  <div className="text-xs text-muted">Title</div>
                  <div className="font-medium">{ticketPreview.title}</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Description</div>
                  <div>{ticketPreview.description}</div>
                </div>
                {ticketPreview.ai_summary && (
                  <div>
                    <div className="text-xs text-muted">AI Summary</div>
                    <div>{ticketPreview.ai_summary}</div>
                  </div>
                )}
                {ticketPreview.ai_recommendation && (
                  <div>
                    <div className="text-xs text-muted">AI Recommendation</div>
                    <div className="font-medium">{ticketPreview.ai_recommendation}</div>
                  </div>
                )}
                {ticketPreview.ai_recommended_actions?.length ? (
                  <div>
                    <div className="text-xs text-muted">AI Actions</div>
                    <ul className="list-disc pl-5">
                      {ticketPreview.ai_recommended_actions.map((a, idx) => (
                        <li key={`${a.action}-${idx}`}>
                          <span className="font-medium">{a.action}</span> — {a.why}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {ticketPreview.ai_ticket_draft?.acceptance_criteria?.length ? (
                  <div>
                    <div className="text-xs text-muted">Acceptance criteria</div>
                    <ul className="list-disc pl-5">
                      {ticketPreview.ai_ticket_draft.acceptance_criteria.map((c, idx) => (
                        <li key={`${c}-${idx}`}>{c}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="pt-2">
                  <button
                    className="btn-secondary"
                    onClick={() => setShowRawTicket((prev) => !prev)}
                  >
                    {showRawTicket ? "Hide raw JSON" : "Show raw JSON"}
                  </button>
                </div>
                {showRawTicket && (
                  <pre className="text-xs bg-bg border border-border rounded-lg p-3 overflow-auto">
{JSON.stringify(ticketPreview, null, 2)}
                  </pre>
                )}
              </div>
            ) : (
              <div className="text-sm text-muted">Generating ticket…</div>
            )}
          </div>
        </>
      )}

      {message && message.type === "error" && (
        <div className="card p-4 text-sm text-red-600">{message.text}</div>
      )}
    </div>
  );
}
