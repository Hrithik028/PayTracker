import { CheckCircle2, CircleAlert, ScanLine } from "lucide-react";

export function StatusBadge({ status }: { status: string }) {
  const config = status === "confirmed"
    ? { label: "Verified", icon: CheckCircle2, classes: "bg-emerald-50 text-emerald-700 border-emerald-200" }
    : status === "needs_review"
      ? { label: "Needs Review", icon: CircleAlert, classes: "bg-amber-50 text-amber-700 border-amber-200" }
      : { label: "Extracted", icon: ScanLine, classes: "bg-blue-50 text-blue-700 border-blue-200" };
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.classes}`}>
      <Icon size={14} aria-hidden="true" />
      {config.label}
    </span>
  );
}

