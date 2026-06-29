import { useEffect, useState } from "react";
import api from "../api/client";

// video_path is an absolute path on the server; we only need the filename to
// hit GET /recordings/{filename}.
const fileName = (p) => (p ? p.split("/").pop() : null);

const cardCls =
  "rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900";

export default function Events() {
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loadingVideo, setLoadingVideo] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function loadEvents() {
    api.get("/events", { params: { limit: 200 } }).then((r) => setEvents(r.data));
  }

  useEffect(() => { loadEvents(); }, []);

  // The recordings endpoint needs the auth header, which a bare <video src>
  // can't send — so fetch it as a blob and hand the player an object URL.
  async function playEvent(ev) {
    setSelected(ev);
    setVideoUrl(null);
    const name = fileName(ev.video_path);
    if (!name) return;
    setLoadingVideo(true);
    try {
      const res = await api.get(`/recordings/${name}`, { responseType: "blob" });
      setVideoUrl(URL.createObjectURL(res.data));
    } catch {
      setVideoUrl(null);
    } finally {
      setLoadingVideo(false);
    }
  }

  async function deleteSelected() {
    if (!selected) return;
    if (!window.confirm(`Delete event #${selected.id} and its clip? This can't be undone.`))
      return;
    setDeleting(true);
    try {
      await api.delete(`/events/${selected.id}`);
      setSelected(null);
      setVideoUrl(null);
      loadEvents();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Events</h1>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* List */}
        <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 lg:col-span-2">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs uppercase text-slate-500 dark:bg-slate-900">
              <tr>
                <th className="px-4 py-2">ID</th>
                <th className="px-4 py-2">Object</th>
                <th className="px-4 py-2">Activity</th>
                <th className="px-4 py-2">Conf.</th>
                <th className="px-4 py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr
                  key={ev.id}
                  onClick={() => playEvent(ev)}
                  className={`cursor-pointer border-t border-slate-200 hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-900 ${
                    selected?.id === ev.id ? "bg-slate-100 dark:bg-slate-900" : "bg-white dark:bg-transparent"
                  }`}
                >
                  <td className="px-4 py-2 text-slate-500">{ev.id}</td>
                  <td className="px-4 py-2">{ev.object || "—"}</td>
                  <td className="px-4 py-2">{ev.activity || "—"}</td>
                  <td className="px-4 py-2">
                    {ev.confidence ? `${(ev.confidence * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {new Date(ev.timestamp + "Z").toLocaleString()}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={5} className="bg-white px-4 py-8 text-center text-slate-500 dark:bg-transparent">
                    No events yet. Run the surveillance pipeline to generate some.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Playback */}
        <div className={cardCls}>
          <h2 className="mb-3 text-sm font-medium text-slate-600 dark:text-slate-300">Playback</h2>
          {!selected && <p className="text-sm text-slate-500">Select an event to play its clip.</p>}
          {selected && (
            <div className="space-y-3">
              {loadingVideo && <p className="text-sm text-slate-500">Loading clip…</p>}
              {videoUrl && (
                <video src={videoUrl} controls autoPlay className="w-full rounded-lg bg-black" />
              )}
              {!loadingVideo && !videoUrl && (
                <p className="text-sm text-red-500 dark:text-red-400">Clip not found on disk.</p>
              )}
              <p className="text-xs text-slate-500">
                Event #{selected.id} · {selected.object || "—"} · {selected.activity || "—"}
              </p>
              <button
                onClick={deleteSelected}
                disabled={deleting}
                className="w-full rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Delete event"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
