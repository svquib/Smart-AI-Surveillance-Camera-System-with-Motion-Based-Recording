const TEAM = ["Saquib Maniyar", "Syed Nouman Quadri", "Ayan Patel", "Samidha Mane"];

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white px-6 py-4 text-center text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900">
      <p className="font-medium text-slate-600 dark:text-slate-400">Developed by</p>
      <p className="mt-1">{TEAM.join("  ·  ")}</p>
      <p className="mt-2 text-slate-400 dark:text-slate-600">
        Smart AI Surveillance System · {new Date().getFullYear()}
      </p>
    </footer>
  );
}
