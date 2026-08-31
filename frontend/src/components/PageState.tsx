import { LoaderCircle } from "lucide-react";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="card flex min-h-48 items-center justify-center gap-3 text-slate-600" role="status">
      <LoaderCircle className="animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="card border-red-200 bg-red-50" role="alert">
      <p className="font-semibold text-red-800">Something needs attention</p>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      {retry && <button className="btn-secondary mt-4" onClick={retry}>Try again</button>}
    </div>
  );
}

