import {
  ArrowRight,
  Banknote,
  Clock3,
  Landmark,
  Plus,
  ReceiptText,
  ShieldPlus,
  TriangleAlert,
  WalletCards,
} from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../services/api";
import { Link } from "../services/navigation";
import type { DashboardData } from "../types";
import { aud, dateLabel } from "../utils/format";

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const load = () => api.dashboard().then(setData).catch((reason) => setError(reason.message));
  useEffect(() => { void load(); }, []);

  if (error) return <ErrorState message={error} retry={load} />;
  if (!data) return <LoadingState label="Loading your local records…" />;
  const stats = [
    ["Total gross pay", aud(data.totals.gross_pay), Banknote],
    ["Total net pay", aud(data.totals.net_pay), WalletCards],
    ["Tax withheld", aud(data.totals.tax_withheld), ReceiptText],
    ["Superannuation", aud(data.totals.superannuation), ShieldPlus],
    ["Confirmed hours", Number(data.totals.confirmed_hours).toFixed(2), Clock3],
    ["Average hourly rate", aud(data.effective_average_hourly_rate), Landmark],
  ] as const;
  const maxMonthly = Math.max(...data.monthly_earnings.map((item) => Number(item.gross_pay)), 1);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="A local summary of records you have explicitly verified."
        actions={<Link className="btn-primary" to="/new"><Plus size={19} /> New pay period</Link>}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {stats.map(([label, value, Icon]) => (
          <section className="card" key={label}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-500">{label}</p>
              <span className="rounded-xl bg-blue-50 p-2.5 text-blue-600"><Icon size={20} /></span>
            </div>
            <p className="mt-3 text-2xl font-bold text-navy-950">{value}</p>
          </section>
        ))}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <section className="card">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-navy-950">Monthly gross earnings</h2>
              <p className="text-sm text-slate-500">Confirmed records only</p>
            </div>
          </div>
          {data.monthly_earnings.length ? (
            <div className="flex h-64 items-end gap-3 overflow-x-auto pt-6">
              {data.monthly_earnings.map((item) => (
                <div className="flex min-w-16 flex-1 flex-col items-center gap-2" key={item.month}>
                  <span className="text-xs font-semibold text-slate-600">{aud(item.gross_pay)}</span>
                  <div className="w-full max-w-20 rounded-t-lg bg-blue-500" style={{ height: `${Math.max(6, (Number(item.gross_pay) / maxMonthly) * 180)}px` }} />
                  <span className="text-xs text-slate-500">{item.month}</span>
                </div>
              ))}
            </div>
          ) : <EmptyDashboard />}
        </section>
        <section className="card">
          <h2 className="text-lg font-bold text-navy-950">Review queue</h2>
          <div className="mt-4 flex items-center gap-4 rounded-xl bg-amber-50 p-4">
            <span className="rounded-full bg-amber-100 p-3 text-amber-700"><TriangleAlert /></span>
            <div><p className="text-2xl font-bold text-amber-900">{data.unresolved_discrepancies}</p><p className="text-sm text-amber-800">Unresolved warnings</p></div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">Differences are prompts for your review. PayTracker does not determine whether a legal underpayment occurred.</p>
        </section>
      </div>
      <section className="card mt-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-navy-950">Recent pay periods</h2>
          <Link className="text-sm font-semibold text-blue-600 hover:text-blue-700" to="/history">View history</Link>
        </div>
        {data.recent_pay_periods.length ? (
          <div className="divide-y divide-slate-100">
            {data.recent_pay_periods.map((period) => (
              <Link className="flex min-h-20 items-center justify-between gap-3 py-3 hover:bg-slate-50" key={period.id} to={`/pay-periods/${period.id}/reconciliation`}>
                <div><p className="font-semibold text-navy-950">{period.employer_name || "Employer not set"}</p><p className="text-sm text-slate-500">{dateLabel(period.start_date)} – {dateLabel(period.end_date)}</p></div>
                <div className="flex items-center gap-3"><StatusBadge status={period.status} /><ArrowRight size={18} className="text-slate-400" /></div>
              </Link>
            ))}
          </div>
        ) : <EmptyDashboard />}
      </section>
    </>
  );
}

function EmptyDashboard() {
  return (
    <div className="grid min-h-40 place-items-center rounded-xl border border-dashed border-slate-300 p-6 text-center">
      <div><p className="font-semibold text-slate-700">No confirmed records yet</p><p className="mt-1 text-sm text-slate-500">Create and verify a pay period to populate this view.</p></div>
    </div>
  );
}
