export function Confidence({ value }: { value?: number }) {
  const score = value ?? 0;
  const classes = score >= 80
    ? "bg-emerald-100 text-emerald-700"
    : score >= 60
      ? "bg-amber-100 text-amber-800"
      : "bg-red-100 text-red-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${classes}`} title="Local extraction confidence">
      {score}% confidence
    </span>
  );
}

