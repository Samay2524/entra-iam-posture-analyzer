import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api";
import { storage } from "../storage";

function Metric({ title, value, subtitle }) {
  return (
    <div className="card p-4">
      <div className="text-sm text-muted">{title}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {subtitle && <div className="text-xs text-muted mt-1">{subtitle}</div>}
    </div>
  );
}

function Donut({ title, percent, caption }) {
  const safe = Math.max(0, Math.min(100, percent || 0));
  const ringStyle = {
    background: `conic-gradient(#0f172a ${safe}%, #e2e8f0 0)`,
  };
  return (
    <div className="card p-4">
      <div className="text-sm text-muted">{title}</div>
      <div className="mt-4 flex items-center gap-4">
        <div className="h-20 w-20 rounded-full p-2" style={ringStyle}>
          <div className="h-full w-full rounded-full bg-white flex items-center justify-center text-sm font-semibold">
            {safe}%
          </div>
        </div>
        <div className="text-xs text-muted">{caption}</div>
      </div>
    </div>
  );
}

function BarList({ title, items }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="card p-4">
      <div className="text-sm text-muted">{title}</div>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div key={item.label}>
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{item.label}</span>
              <span>{item.value}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-[#e8e5dd]">
              <div
                className="h-2 rounded-full bg-[#0f172a]"
                style={{ width: `${Math.round((item.value / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const FILTERS_KEY = "iam.dashboard.filters";
const LAST_IDENTITY_KEY = "iam.identity.lastSelected";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [identities, setIdentities] = useState([]);
  const [selectedId, setSelectedId] = useState(() => {
    const stored = storage.readJson(LAST_IDENTITY_KEY, null);
    return stored?.id || "";
  });
  const [details, setDetails] = useState(null);
  const [aiPacket, setAiPacket] = useState(null);
  const [identityTasks, setIdentityTasks] = useState([]);
  const [ticketPreview, setTicketPreview] = useState(null);
  const [showRawTicket, setShowRawTicket] = useState(false);
  const [autoProcessedForId, setAutoProcessedForId] = useState("");
  const [autoCreatedForId, setAutoCreatedForId] = useState("");
  const [autoTaskId, setAutoTaskId] = useState("");
  const [reportSummary, setReportSummary] = useState(null);
  const [reportExports, setReportExports] = useState([]);
  const [filters, setFilters] = useState(() =>
    storage.readJson(FILTERS_KEY, {
      status: "",
      priority: "",
      task_type: "",
      identity_type: "",
      severity: "",
    })
  );
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
  const hasRiskFindings = useMemo(() => {
    const findings = details?.findings || [];
    if (!findings.length) return false;
    return findings.some((f) => ["HIGH", "CRIT"].includes(f.severity));
  }, [details]);

  useEffect(() => {
    apiGet("/reports/summary").then(setSummary).catch(() => setSummary(null));
    apiGet("/identities").then(setIdentities).catch(() => setIdentities([]));
    apiGet("/export/reports")
      .then((result) => setReportExports(result.reports || []))
      .catch(() => setReportExports([]));
    apiGet("/reports/summary").then(setReportSummary).catch(() => setReportSummary(null));
  }, []);

  useEffect(() => {
    apiGet("/tasks", filters).then(setTasks).catch(() => setTasks([]));
  }, [filters]);

  useEffect(() => {
    storage.writeJson(FILTERS_KEY, filters);
  }, [filters]);

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

  const handle = async (fn) => {
    try {
      return await fn();
    } catch {
      return null;
    }
  };

  const refreshExports = async () => {
    const result = await handle(() => apiGet("/export/reports"));
    if (result?.reports) setReportExports(result.reports);
  };

  const refreshTasks = async () => {
    if (!selectedId) return [];
    const result = await handle(() => apiGet("/tasks", { identity_id: selectedId }));
    if (result) setIdentityTasks(result);
    return result || [];
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
    if (!hasRiskFindings) return;
    if (autoProcessedForId === String(selectedId)) return;
    setAutoProcessedForId(String(selectedId));
    const ai = await handle(() => apiPost(`/ai/${selectedId}`));
    if (ai?.packet) setAiPacket(ai.packet);
    const exported = await handle(() => apiPost(`/export/ticket/${taskId}`));
    if (exported) {
      const preview = await handle(() => apiGet(`/export/ticket/${taskId}/preview`));
      if (preview?.payload) setTicketPreview(preview.payload);
      await refreshExports();
    }
  };

  const downloadReportPdf = (report) => {
    const win = window.open("", "_blank", "width=900,height=700");
    if (!win) return;
    const html = `
      <html>
        <head>
          <title>${report.title || "IAM Report"}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }
            h1 { font-size: 20px; margin-bottom: 8px; }
            h2 { font-size: 14px; margin-top: 18px; text-transform: uppercase; letter-spacing: 0.04em; color: #64748b; }
            p, li { font-size: 13px; line-height: 1.5; }
            .meta { font-size: 12px; color: #64748b; margin-bottom: 16px; }
            .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 12px; }
          </style>
        </head>
        <body>
          <h1>${report.title || "IAM Report"}</h1>
          <div class="meta">Generated at: ${report.generated_at || "—"} • Identity: ${report.identity_id || "—"}</div>
          <div class="card">
            <h2>Summary</h2>
            <p>${report.ai_summary || report.description || "—"}</p>
          </div>
          <div class="card">
            <h2>Recommendation</h2>
            <p>${report.ai_recommendation || "—"}</p>
          </div>
          <div class="card">
            <h2>Actions</h2>
            <ul>
              ${(report.ai_recommended_actions || [])
                .map((a) => `<li><strong>${a.action}</strong> — ${a.why}</li>`)
                .join("")}
            </ul>
          </div>
          <div class="card">
            <h2>Acceptance Criteria</h2>
            <ul>
              ${(report.ai_ticket_draft?.acceptance_criteria || [])
                .map((c) => `<li>${c}</li>`)
                .join("")}
            </ul>
          </div>
        </body>
      </html>`;
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
  };

  const downloadAllReportsPdf = () => {
    const win = window.open("", "_blank", "width=1000,height=800");
    if (!win) return;
    const blocks = reportExports
      .map(
        (report) => `
        <section class="card">
          <h1>${report.title || "IAM Report"}</h1>
          <div class="meta">Generated at: ${report.generated_at || "—"} • Identity: ${report.identity_id || "—"}</div>
          <h2>Summary</h2>
          <p>${report.ai_summary || report.description || "—"}</p>
          <h2>Recommendation</h2>
          <p>${report.ai_recommendation || "—"}</p>
          <h2>Actions</h2>
          <ul>
            ${(report.ai_recommended_actions || [])
              .map((a) => `<li><strong>${a.action}</strong> — ${a.why}</li>`)
              .join("")}
          </ul>
          <h2>Acceptance Criteria</h2>
          <ul>
            ${(report.ai_ticket_draft?.acceptance_criteria || [])
              .map((c) => `<li>${c}</li>`)
              .join("")}
          </ul>
        </section>`
      )
      .join("<div class=\"page-break\"></div>");
    const html = `
      <html>
        <head>
          <title>IAM Reports</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }
            h1 { font-size: 18px; margin-bottom: 6px; }
            h2 { font-size: 12px; margin-top: 16px; text-transform: uppercase; letter-spacing: 0.04em; color: #64748b; }
            p, li { font-size: 12px; line-height: 1.5; }
            .meta { font-size: 11px; color: #64748b; margin-bottom: 10px; }
            .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 16px; }
            .page-break { page-break-after: always; }
          </style>
        </head>
        <body>
          ${blocks || "<p>No reports available.</p>"}
        </body>
      </html>`;
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    win.print();
  };

  useEffect(() => {
    if (!selectedId) return;
    if (details && !hasRiskFindings) return;
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
    if (!selectedId || !latestTaskId) return;
    autoGenerateReport(latestTaskId);
  }, [selectedId, latestTaskId]);

  const onOpenIdentity = (identityId) => {
    if (!identityId) return;
    storage.writeJson(LAST_IDENTITY_KEY, { id: String(identityId) });
    setSelectedId(String(identityId));
  };

  const activeFilterCount = useMemo(() => {
    return Object.values(filters).filter(Boolean).length;
  }, [filters]);

  const tasksByStatus = useMemo(() => {
    const counts = tasks.reduce((acc, t) => {
      acc[t.status || "UNKNOWN"] = (acc[t.status || "UNKNOWN"] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value);
  }, [tasks]);

  const tasksByType = useMemo(() => {
    const counts = tasks.reduce((acc, t) => {
      acc[t.task_type || "UNKNOWN"] = (acc[t.task_type || "UNKNOWN"] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value);
  }, [tasks]);

  const riskCompletion = useMemo(() => {
    const total = summary?.identities || 0;
    const high = summary?.high_risk_identities || 0;
    if (!total) return 0;
    const safe = Math.max(0, total - high);
    return Math.round((safe / total) * 100);
  }, [summary]);

  const topFindings = useMemo(() => {
    const entries = reportSummary?.top_findings || [];
    const counts = entries.reduce((acc, item) => {
      const key = `${item.code} (${item.severity})`;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }, [reportSummary]);

  const shortText = (text, max = 220) => {
    if (!text) return "—";
    return text.length > max ? `${text.slice(0, max)}…` : text;
  };

  return (
    <div className="space-y-6">
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 xl:grid-cols-7 gap-3">
          <Metric title="Identities" value={summary.identities} subtitle="Total identities" />
          <Metric title="High/Critical" value={summary.high_risk_identities} subtitle="Needs attention" />
          <Metric title="Open Tasks" value={summary.open_tasks} subtitle="Active reviews" />
          <Metric title="P1 Tasks" value={summary.p1_tasks} subtitle="Urgent items" />
          <Donut
            title="Risk Health"
            percent={riskCompletion}
            caption="Healthy identities"
          />
          <BarList title="Tasks by status" items={tasksByStatus.slice(0, 5)} />
          <BarList title="Tasks by type" items={tasksByType.slice(0, 5)} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.8fr,1.2fr] gap-3 lg:items-stretch">
        <div className="card p-4 space-y-3 flex flex-col h-full">
          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold">Recent tasks</div>
            <div className="text-xs text-muted">
              {activeFilterCount ? `${activeFilterCount} filters active` : "No filters"}
            </div>
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Filters</summary>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm mt-3">
            <select
              className="border border-border rounded-lg px-3 py-2"
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            >
              <option value="">Status</option>
              <option>OPEN</option>
              <option>IN_REVIEW</option>
              <option>DONE</option>
              <option>ESCALATED</option>
            </select>
            <select
              className="border border-border rounded-lg px-3 py-2"
              value={filters.priority}
              onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
            >
              <option value="">Priority</option>
              <option>P1</option>
              <option>P2</option>
              <option>P3</option>
            </select>
            <select
              className="border border-border rounded-lg px-3 py-2"
              value={filters.task_type}
              onChange={(e) => setFilters({ ...filters, task_type: e.target.value })}
            >
              <option value="">Task Type</option>
              <option>ACCESS_REVIEW</option>
              <option>REMEDIATE</option>
              <option>PAM_ONBOARD</option>
              <option>ROTATE_SECRET</option>
              <option>ASSIGN_OWNER</option>
              <option>DISABLE_ACCOUNT</option>
            </select>
            <select
              className="border border-border rounded-lg px-3 py-2"
              value={filters.identity_type}
              onChange={(e) => setFilters({ ...filters, identity_type: e.target.value })}
            >
              <option value="">Identity Type</option>
              <option>USER</option>
              <option>SERVICE_PRINCIPAL</option>
            </select>
            <select
              className="border border-border rounded-lg px-3 py-2"
              value={filters.severity}
              onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
            >
              <option value="">Severity</option>
              <option>LOW</option>
              <option>MED</option>
              <option>HIGH</option>
              <option>CRIT</option>
            </select>
            </div>
          </details>

          <div className="overflow-auto border border-border rounded-lg flex-1 min-h-0">
            <table className="min-w-full text-sm">
              <thead className="bg-[#faf9f7] text-muted">
                <tr>
                  <th className="text-left px-3 py-2">ID</th>
                  <th className="text-left px-3 py-2">Identity</th>
                  <th className="text-left px-3 py-2">Type</th>
                  <th className="text-left px-3 py-2">Severity</th>
                  <th className="text-left px-3 py-2">Task</th>
                  <th className="text-left px-3 py-2">Priority</th>
                  <th className="text-left px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr
                    key={t.id}
                    className="border-t border-border cursor-pointer hover:bg-white/70"
                    onClick={() => onOpenIdentity(t.identity_id)}
                  >
                    <td className="px-3 py-2">{t.id}</td>
                    <td className="px-3 py-2">{t.identity_id}</td>
                    <td className="px-3 py-2">{t.identity_type}</td>
                    <td className="px-3 py-2">{t.max_severity || "—"}</td>
                    <td className="px-3 py-2">{t.task_type}</td>
                    <td className="px-3 py-2">{t.priority}</td>
                    <td className="px-3 py-2">{t.status}</td>
                  </tr>
                ))}
                {!tasks.length && (
                  <tr>
                    <td colSpan="7" className="px-3 py-6 text-center text-muted">
                      No tasks found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-3">
          <div className="card p-4 space-y-3">
            <div className="text-lg font-semibold">Identity Review</div>
            <div className="text-sm text-muted">
              Select an identity to auto-generate its AI summary and report.
            </div>
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
            {details ? (
              <div className="border border-border rounded-lg p-3 text-sm">
                <div className="font-medium">{details.display_name}</div>
                <div className="text-xs text-muted">{details.upn || "No sign-in name"}</div>
                <div className="mt-2 text-xs text-muted">
                  Findings: {findingCount} • Roles: {roleCount}
                </div>
              </div>
            ) : (
              <div className="text-xs text-muted">Select an identity to see details.</div>
            )}
          </div>
          <div className="card p-4">
            <div className="text-lg font-semibold mb-3">Generated Reports</div>
            <div className="text-xs text-muted mb-2">
              Each report is created by AI and can be downloaded as a PDF.
            </div>
            <div className="mb-3">
              <button className="btn-primary" onClick={downloadAllReportsPdf}>
                Download All Reports (PDF)
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm max-h-64 overflow-auto">
              {reportExports.slice(0, 6).map((report) => (
                <details key={report.file} className="border border-border rounded-lg p-3">
                  <summary className="cursor-pointer">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{report.title || "IAM Report"}</div>
                        <div className="text-xs text-muted">
                          Recommendation: {report.ai_recommendation || "—"}
                        </div>
                      </div>
                      <div className="text-xs text-muted">{report.generated_at || "—"}</div>
                    </div>
                  </summary>
                  <div className="mt-3 space-y-2">
                    <div className="text-xs text-muted">Summary</div>
                    <div>{shortText(report.ai_summary || report.description, 220)}</div>
                  </div>
                </details>
              ))}
              {!reportExports.length && (
                <div className="text-sm text-muted">No reports yet.</div>
              )}
            </div>
          </div>
          <div className="card p-4">
            <div className="text-lg font-semibold mb-3">Run Report Summary</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="border border-border rounded-lg p-3">
                <div className="text-xs text-muted">Identities</div>
                <div className="text-lg font-semibold">{reportSummary?.identities ?? "—"}</div>
              </div>
              <div className="border border-border rounded-lg p-3">
                <div className="text-xs text-muted">High/Critical</div>
                <div className="text-lg font-semibold">{reportSummary?.high_risk_identities ?? "—"}</div>
              </div>
              <div className="border border-border rounded-lg p-3">
                <div className="text-xs text-muted">Open Tasks</div>
                <div className="text-lg font-semibold">{reportSummary?.open_tasks ?? "—"}</div>
              </div>
              <div className="border border-border rounded-lg p-3">
                <div className="text-xs text-muted">P1 Tasks</div>
                <div className="text-lg font-semibold">{reportSummary?.p1_tasks ?? "—"}</div>
              </div>
            </div>
            {topFindings.length ? (
              <div className="mt-3">
                <BarList title="Top Findings" items={topFindings} />
              </div>
            ) : (
              <div className="text-xs text-muted mt-3">No findings data yet.</div>
            )}
          </div>
        </div>
      </div>

      {details && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div className="card p-4 space-y-3">
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

              <div className="card p-4 space-y-3">
                <div className="text-lg font-semibold">Findings</div>
                <div className="text-sm text-muted">
                  These are the issues detected for this identity.
                </div>
                <div className="space-y-3">
                  {(details.findings || []).slice(0, 3).map((f, idx) => (
                    <div key={`${f.code}-${idx}`} className="border border-border rounded-lg p-3">
                      <div className="font-semibold">{f.title}</div>
                      <div className="text-xs text-muted">Severity: {f.severity}</div>
                      <div className="text-xs text-muted mt-1">
                        Evidence: {JSON.stringify(f.evidence || f.evidence_json || {})}
                      </div>
                    </div>
                  ))}
                  {details.findings?.length > 3 && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-muted">View all findings</summary>
                      <div className="space-y-3 mt-3">
                        {(details.findings || []).slice(3).map((f, idx) => (
                          <div key={`${f.code}-more-${idx}`} className="border border-border rounded-lg p-3">
                            <div className="font-semibold">{f.title}</div>
                            <div className="text-xs text-muted">Severity: {f.severity}</div>
                            <div className="text-xs text-muted mt-1">
                              Evidence: {JSON.stringify(f.evidence || f.evidence_json || {})}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  {!details.findings?.length && (
                    <div className="text-sm text-muted">No findings for this identity.</div>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[1fr,1fr] gap-3">
              <div className="card p-4 space-y-3">
                <div className="text-lg font-semibold">AI Summary</div>
                <div className="text-xs text-muted">
                  Generated automatically when you select an identity.
                </div>
                {aiPacket ? (
                  <div className="border border-border rounded-lg p-4 space-y-3 text-sm">
                    <div className="text-xs text-muted uppercase tracking-wide">Summary</div>
                    <div className="font-medium">{shortText(aiPacket.summary, 260)}</div>
                    <details className="text-sm">
                      <summary className="cursor-pointer text-muted">View full AI summary</summary>
                      <div className="mt-3 space-y-4 text-base leading-relaxed">
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
                    </details>
                  </div>
                ) : (
                  <div className="text-xs text-muted">Generating AI summary…</div>
                )}
              </div>

              <div className="card p-4 space-y-3">
                <div className="text-lg font-semibold">Auto-generated Ticket</div>
                <div className="text-sm text-muted">
                  Created automatically from the AI summary and saved as a report file.
                </div>
                {!hasRiskFindings ? (
                  <div className="text-sm text-muted">
                    No HIGH/CRIT findings for this identity, so no ticket was created.
                  </div>
                ) : ticketPreview ? (
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
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
