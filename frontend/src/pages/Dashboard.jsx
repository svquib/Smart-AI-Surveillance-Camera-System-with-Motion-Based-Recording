import { useEffect, useState } from "react";
import api, { API_BASE } from "../api/client";

// Small coloured pill used for activity / status throughout the app.
function Badge({ children, tone = "slate" }) {
  const tones = {
    slate: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
    green: "bg-emerald-200 text-emerald-800 dark:bg-emerald-700 dark:text-emerald-100",
    amber: "bg-amber-200 text-amber-800 dark:bg-amber-600 dark:text-amber-50",
    red: "bg-red-200 text-red-800 dark:bg-red-700 dark:text-red-100",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function activityTone(activity) {
  if (["falling", "abnormal"].includes(activity)) return "red";
  if (["running", "walking"].includes(activity)) return "amber";
  if (activity === "standing") return "green";
  return "slate";
}

const cardCls =
  "rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900";

function StatCard({ label, value, tone }) {
  return (
    <div className={cardCls}>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone || ""}`}>{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const [latest, setLatest] = useState(null);
  const [stats, setStats] = useState({ events: 0, alerts: 0, emergencies: 0 });
  const [liveOn, setLiveOn] = useState(false);

  // Poll the API for the most recent event + a few counts every 3s.
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const [events, alerts] = await Promise.all([
          api.get("/events", { params: { limit: 100 } }),
          api.get("/alerts"),
        ]);
        if (!active) return;
        setLatest(events.data[0] || null);
        setStats({
          events: events.data.length,
          alerts: alerts.data.length,
          emergencies: alerts.data.filter((a) => a.type === "emergency").length,
        });
      } catch {
        /* interceptor handles auth errors */
      }
    }
    refresh();
    const id = setInterval(refresh, 3000);
    return () => { active = false; clearInterval(id); };
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total events" value={stats.events} />
        <StatCard label="Active alerts" value={stats.alerts} tone="text-amber-500" />
        <StatCard label="Emergencies" value={stats.emergencies} tone="text-red-500" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Live feed */}
        <div className={`lg:col-span-2 ${cardCls}`}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-600 dark:text-slate-300">Live feed</h2>
            <button
              onClick={() => setLiveOn((v) => !v)}
              className="rounded-md bg-slate-200 px-3 py-1 text-xs hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700"
            >
              {liveOn ? "Stop" : "Start"} stream
            </button>
          </div>
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-lg bg-black">
            {liveOn ? (
              <img
                src={`${API_BASE}/camera/live`}
                alt="Live camera"
                className="h-full w-full object-contain"
              />
            ) : (
              <p className="text-sm text-slate-400">
                Stream stopped. Press start to view the camera.
              </p>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Note: don't run the live stream and the detection pipeline at the same
            time — they share the webcam.
          </p>
        </div>

        {/* Current status from the latest event */}
        <div className={cardCls}>
          <h2 className="mb-3 text-sm font-medium text-slate-600 dark:text-slate-300">
            Latest detection
          </h2>
          {latest ? (
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Object</dt>
                <dd>{latest.object || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Confidence</dt>
                <dd>{latest.confidence ? `${(latest.confidence * 100).toFixed(0)}%` : "—"}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500">Activity</dt>
                <dd><Badge tone={activityTone(latest.activity)}>{latest.activity || "—"}</Badge></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Time</dt>
                <dd className="text-slate-500">
                  {new Date(latest.timestamp + "Z").toLocaleString()}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">No events yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
