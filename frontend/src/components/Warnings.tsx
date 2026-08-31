import { CircleAlert } from "lucide-react";
import type { Warning } from "../types";

export function Warnings({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) {
    return <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-800">No validation warnings detected.</div>;
  }
  return (
    <div className="space-y-2" aria-live="polite">
      {warnings.map((warning, index) => (
        <div key={`${warning.code}-${index}`} className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <CircleAlert className="mt-0.5 shrink-0" size={18} aria-hidden="true" />
          <span>{warning.message}</span>
        </div>
      ))}
    </div>
  );
}

