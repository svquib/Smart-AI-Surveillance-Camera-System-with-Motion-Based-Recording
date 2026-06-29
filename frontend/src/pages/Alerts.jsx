import { useEffect, useState } from "react";
import api from "../api/client";

const typeTone = {
  emergency: "border-red-400 bg-red-50 dark:border-red-600 dark:bg-red-950/40",
  suspicious: "border-amber-400 bg-amber-50 dark:border-amber-600 dark:bg-amber-950/30",
  info: "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900",
};

const typeBadge = {
  emergency: "bg-red-200 text-red-800 dark:bg-red-700 dark:text-red-100",
  suspicious: "bg-amber-200 text-amber-800 dark:bg-amber-600 dark:text-amber-50",
  info: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
};

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState("all");

  async function load() {
    const r = await api.get("/alerts");
    setAlerts(r.data);
  }

  useEffect(() => { load(); }, []);

  async function setStatus(id, status) {
    await api.patch(`/alerts/${id}`, { status });
    load();
  }

  const shown = filter === "all" ? alerts : alerts.filter((a) => a.status === filter);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Alerts</h1>
        <div className="flex gap-1 text-xs">
          {["all", "new", "acknowledged", "resolved"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-3 py-1 capitalize ${
                filter === f
                  ? "bg-slate-300 text-slate-900 dark:bg-slate-700 dark:text-white"
                  : "bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {shown.map((a) => (
          <div key={a.id} className={`rounded-xl border p-4 ${typeTone[a.type] || typeTone.info}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="mb-1 flex items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${typeBadge[a.type] || typeBadge.info}`}>
                    {a.type}
                  </span>
                  <span className="text-xs text-slate-500">
                    {new Date(a.created_at + "Z").toLocaleString()}
                  </span>
                </div>
                <p className="text-sm">{a.message}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <span className="text-xs uppercase text-slate-500">{a.status}</span>
                <div className="flex gap-1">
                  {a.status !== "acknowledged" && (
                    <button
                      onClick={() => setStatus(a.id, "acknowledged")}
                      className="rounded-md bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700"
                    >
                      Ack
                    </button>
                  )}
                  {a.status !== "resolved" && (
                    <button
                      onClick={() => setStatus(a.id, "resolved")}
                      className="rounded-md bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-500"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
        {shown.length === 0 && (
          <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900">
            No alerts to show.
          </p>
        )}
      </div>
    </div>
  );
}
