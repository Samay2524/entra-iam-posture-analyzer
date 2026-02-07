import { useState } from "react";
import { apiGet, apiPost } from "../api";
import { storage } from "../storage";

function StatusCard({ title, value, subtitle, masked }) {
  const display = masked && value && value !== "—"
    ? `${value.slice(0, 6)}...${value.slice(-4)}`
    : value;
  const onCopy = async () => {
    if (!value || value === "—") return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // ignore
    }
  };
  return (
    <div className="card p-4">
      <div className="text-sm text-muted">{title}</div>
      <div className="flex items-center justify-between gap-2 mt-1">
        <div className="text-lg font-semibold truncate">{display}</div>
        {masked && value && value !== "—" && (
          <button className="btn-secondary" onClick={onCopy}>
            Copy
          </button>
        )}
      </div>
      {subtitle && <div className="text-xs text-muted mt-1">{subtitle}</div>}
    </div>
  );
}

export default function Setup() {
  const [message, setMessage] = useState(null);
  const [permissions, setPermissions] = useState(null);
  const [lastRun, setLastRun] = useState(() =>
    storage.readJson("iam.setup.lastRun", null)
  );

  const handle = async (fn, label) => {
    setMessage(null);
    try {
      const result = await fn();
      if (label) {
        const record = { label, at: new Date().toISOString() };
        storage.writeJson("iam.setup.lastRun", record);
        setLastRun(record);
      }
      setMessage({ type: "success", text: `${label || "Completed"} successfully.` });
      return result;
    } catch (err) {
      setMessage({ type: "error", text: err.message });
      return null;
    }
  };

  const runTest = async () => {
    const result = await apiGet("/ingest/test");
    setPermissions(result);
    return result;
  };

  const runAll = async () => {
    const ok1 = await handle(runTest, "Verify Connection");
    if (!ok1) return;
    const ok2 = await handle(() => apiPost("/ingest/run"), "Sync Entra Data");
    if (!ok2) return;
    await handle(() => apiPost("/analyze/run"), "Generate Reports");
  };

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="text-xl font-semibold">Connect Your Entra Tenant</div>
        <div className="text-sm text-muted mt-1">
          Set this up once, then you can run reports anytime.
        </div>
        <div className="mt-3">
          <div className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-700 border border-emerald-200">
            Connected ✓ • Reports ready ✓
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="border border-border rounded-lg p-3">
            <div className="font-semibold">1) Register app</div>
            <div className="text-xs text-muted">Create an app in Entra with Application permissions.</div>
          </div>
          <div className="border border-border rounded-lg p-3">
            <div className="font-semibold">2) Add secrets</div>
            <div className="text-xs text-muted">Set `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` in `.env`.</div>
          </div>
          <div className="border border-border rounded-lg p-3">
            <div className="font-semibold">3) Verify & run</div>
            <div className="text-xs text-muted">Click Verify → Sync → Generate Reports.</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusCard title="Tenant ID" value={import.meta.env.VITE_TENANT_ID || "—"} subtitle="Entra Directory ID" masked />
        <StatusCard title="Client ID" value={import.meta.env.VITE_CLIENT_ID || "—"} subtitle="App Registration ID" masked />
        <StatusCard
          title="AI Key"
          value={import.meta.env.VITE_GEMINI_STATUS || "Configured via .env"}
          subtitle="Gemini API key"
        />
      </div>

      <div className="card p-6">
        <div className="text-lg font-semibold">Quick Setup</div>
        <div className="text-sm text-muted">
          Click these in order. The app will do the rest.
        </div>
        {lastRun && (
          <div className="text-xs text-muted mt-2">
            Last action: {lastRun.label} • {new Date(lastRun.at).toLocaleString()}
          </div>
        )}
        <div className="mt-4">
          <button className="btn-primary w-full" onClick={runAll}>
            Start (Verify → Sync → Generate)
          </button>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <button className="btn-primary" onClick={() => handle(runTest, "Verify Connection")}>
            1) Verify Connection
          </button>
          <button
            className="btn-primary"
            onClick={() => handle(() => apiPost("/ingest/run"), "Sync Entra Data")}
          >
            2) Sync Entra Data
          </button>
          <button
            className="btn-primary"
            onClick={() => handle(() => apiPost("/analyze/run"), "Generate Reports")}
          >
            3) Generate Reports
          </button>
        </div>

        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted">Advanced options</summary>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              className="btn-secondary"
              onClick={() => handle(() => apiPost("/ingest/demo_seed"), "Use Demo Data")}
            >
              Use Demo Data
            </button>
            <button
              className="btn-secondary"
              onClick={() => handle(() => apiPost("/ingest/clear_cache"), "Clear Token Cache")}
            >
              Clear Token Cache
            </button>
            <button className="btn-secondary" onClick={() => handle(() => apiPost("/reset"), "Reset Database")}>
              Reset Database
            </button>
          </div>
        </details>
      </div>

      {permissions && permissions.permissions && (
        <details className="card p-6 text-sm">
          <summary className="cursor-pointer text-muted">View permissions details</summary>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            {Object.entries(permissions.permissions).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between border-b border-border py-2">
                <div className="text-muted">{key}</div>
                <div className={value.includes("✅") ? "text-green-600" : "text-amber-600"}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {message && (
        <div className={`card p-4 text-sm ${message.type === "error" ? "text-red-600" : "text-green-600"}`}>
          {message.text}
        </div>
      )}
    </div>
  );
}
