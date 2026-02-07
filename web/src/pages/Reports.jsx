import { useEffect, useState } from "react";
import { apiGet } from "../api";

export default function Reports() {
  const [audit, setAudit] = useState([]);
  const [exports, setExports] = useState(null);

  useEffect(() => {
    apiGet("/audit").then(setAudit).catch(() => setAudit([]));
    apiGet("/export/files").then(setExports).catch(() => setExports(null));
  }, []);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="text-2xl font-semibold">Reports</div>
        <div className="text-sm text-muted mt-1">Audit-ready exports and logs.</div>
      </div>

      <div className="card p-6">
        <div className="text-lg font-semibold mb-3">Audit Events</div>
        <div className="overflow-auto border border-border rounded-lg">
          <table className="min-w-full text-sm">
            <thead className="bg-bg text-muted">
              <tr>
                <th className="text-left px-3 py-2">Time</th>
                <th className="text-left px-3 py-2">Actor</th>
                <th className="text-left px-3 py-2">Event</th>
                <th className="text-left px-3 py-2">Entity</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="px-3 py-2">{e.ts}</td>
                  <td className="px-3 py-2">{e.actor}</td>
                  <td className="px-3 py-2">{e.event_type}</td>
                  <td className="px-3 py-2">{e.entity_type}</td>
                </tr>
              ))}
              {!audit.length && (
                <tr>
                  <td colSpan="4" className="px-3 py-6 text-center text-muted">
                    No audit events yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-6">
        <div className="text-lg font-semibold mb-3">Exports</div>
        <pre className="text-xs bg-bg border border-border rounded-lg p-3 overflow-auto">
{JSON.stringify(exports, null, 2)}
        </pre>
      </div>
    </div>
  );
}
