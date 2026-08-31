import { Download, ExternalLink, FilePenLine, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../services/api";
import { Link } from "../services/navigation";
import type { PayPeriodSummary } from "../types";
import { aud, dateLabel } from "../utils/format";

export function History() {
  const [periods, setPeriods] = useState<PayPeriodSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [error, setError] = useState("");
  const load = () => api.listPeriods().then(setPeriods).catch((reason) => setError(reason.message));
  useEffect(() => { void load(); }, []);
  const filtered = useMemo(() => (periods ?? []).filter((period) => {
    const matchesQuery = `${period.employer_name ?? ""} ${period.start_date ?? ""} ${period.end_date ?? ""}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (status === "all" || period.status === status);
  }), [periods, query, status]);
  const remove = async (period: PayPeriodSummary) => {
    if (!window.confirm(`Delete the ${period.employer_name || "unnamed"} pay period? This removes its database record and PayTracker's generated document copies. Your original source files are not touched.`)) return;
    try { await api.deletePeriod(period.id); setPeriods((current) => current?.filter((item) => item.id !== period.id) ?? null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete record"); }
  };
  const exportOne = async (period: PayPeriodSummary) => {
    try { const result = await api.export(period.id); window.location.assign(result.download_url); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Only confirmed records can be exported"); }
  };

  if (error && !periods) return <ErrorState message={error} retry={load} />;
  if (!periods) return <LoadingState label="Loading history…" />;
  return (
    <>
      <PageHeader title="History" description="Search, review and export records stored in your local SQLite database." />
      <section className="card">
        <div className="grid gap-3 sm:grid-cols-[1fr_220px]">
          <label className="relative"><span className="sr-only">Search by employer or date</span><Search className="absolute left-3 top-3 text-slate-400" size={19} /><input className="input pl-10" placeholder="Search employer or date" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <label><span className="sr-only">Filter by status</span><select className="input" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="draft">Extracted</option><option value="needs_review">Needs Review</option><option value="confirmed">Verified</option></select></label>
        </div>
        {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
        <div className="table-wrap mt-5">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600"><tr><th className="p-3">Employer</th><th className="p-3">Period</th><th className="p-3">Gross</th><th className="p-3">Hours</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((period) => (
                <tr key={period.id}>
                  <td className="p-3 font-semibold text-navy-950">{period.employer_name || "Not set"}</td>
                  <td className="p-3 text-slate-600">{dateLabel(period.start_date)} – {dateLabel(period.end_date)}</td>
                  <td className="p-3 font-semibold tabular-nums">{aud(period.gross_pay)}</td>
                  <td className="p-3 tabular-nums">{Number(period.screenshot_hours).toFixed(2)}</td>
                  <td className="p-3"><StatusBadge status={period.status} /></td>
                  <td className="p-3"><div className="flex gap-1">
                    <Link className="rounded-lg p-2 text-blue-600 hover:bg-blue-50" to={`/pay-periods/${period.id}/reconciliation`} aria-label="Open record"><ExternalLink size={18} /></Link>
                    <Link className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" to={`/pay-periods/${period.id}/payslip`} aria-label="Edit record"><FilePenLine size={18} /></Link>
                    <button className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-30" disabled={period.status !== "confirmed"} onClick={() => exportOne(period)} aria-label="Export record"><Download size={18} /></button>
                    <button className="rounded-lg p-2 text-red-600 hover:bg-red-50" onClick={() => remove(period)} aria-label="Delete record"><Trash2 size={18} /></button>
                  </div></td>
                </tr>
              ))}
              {!filtered.length && <tr><td className="p-10 text-center text-slate-500" colSpan={6}>No pay periods match this filter.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
