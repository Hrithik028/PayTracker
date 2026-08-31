import {
  Calculator,
  Check,
  CircleCheck,
  Download,
  Pencil,
  Scale,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { StatusBadge } from "../components/StatusBadge";
import { Warnings } from "../components/Warnings";
import { usePayPeriod } from "../hooks/usePayPeriod";
import { api } from "../services/api";
import { navigate, payPeriodIdFromPath } from "../services/navigation";
import type { PayPeriod } from "../types";
import { aud, dateLabel, decimalHoursLabel, hoursAndMinutes, weekdayLabel } from "../utils/format";
import { Progress } from "./ReviewPayslip";

export function Reconciliation() {
  const id = payPeriodIdFromPath();
  const { period, loading, error, reload } = usePayPeriod(id);
  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState("");
  if (loading) return <LoadingState label="Calculating reconciliation…" />;
  if (error || !period) return <ErrorState message={error || "Pay period not found"} retry={reload} />;
  const result = period.reconciliation;
  const categoryRows = hoursByCategory(period);
  const dailyRows = [...period.shifts].sort((left, right) =>
    `${left.shift_date ?? ""}-${left.start_time ?? ""}`.localeCompare(
      `${right.shift_date ?? ""}-${right.start_time ?? ""}`,
    ),
  );
  const lastRowForCategory = new Map<string, number>();
  dailyRows.forEach((shift, index) => lastRowForCategory.set(shift.category, index));
  const categoryDifference = new Map(
    categoryRows.map((row) => [row.category, row.difference]),
  );

  const confirm = async () => {
    setWorking(true); setActionError("");
    try { await api.confirmPeriod(period.id); navigate("/"); }
    catch (reason) { setActionError(reason instanceof Error ? reason.message : "Unable to confirm this record"); }
    finally { setWorking(false); }
  };
  const exportOne = async () => {
    setWorking(true); setActionError("");
    try {
      const exported = await api.export(period.id);
      window.location.assign(exported.download_url);
    } catch (reason) { setActionError(reason instanceof Error ? reason.message : "Unable to export"); }
    finally { setWorking(false); }
  };

  return (
    <>
      <PageHeader title="Reconciliation" description="Compare the locally calculated values with the payslip. Differences require your judgement." actions={<StatusBadge status={period.status} />} />
      <Progress current={3} />
      <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <div className="flex gap-3"><TriangleAlert className="shrink-0 text-amber-700" /><div><h2 className="font-bold text-amber-900">Potential discrepancy—review required</h2><p className="mt-1 text-sm leading-6 text-amber-800">A difference is not a legal conclusion. PayTracker does not determine whether an underpayment occurred.</p></div></div>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ComparisonCard
          title="Hours comparison"
          rows={[
            ["Payslip hours", decimalHoursLabel(result.payslip_hours)],
            ["Screenshot hours", decimalHoursLabel(result.screenshot_hours)],
            ["Difference (screenshots − payslip)", signedHoursWithMinutes(Number(result.hours_difference))],
          ]}
          state={result.hours_state}
        />
        <ComparisonCard
          title="Pay item comparison"
          rows={[
            ["Hours × rate", aud(result.calculated_amount)],
            ["Paid line-item amounts", aud(result.paid_line_item_amount)],
            ["Difference", aud(result.amount_difference)],
          ]}
          state={result.amount_state}
        />
      </div>
      <EstimatedPayCard result={result} />
      <section className="card mt-6">
        <h2 className="text-lg font-bold text-navy-950">Hours by pay category</h2>
        <p className="mt-1 text-sm text-slate-500">This breakdown shows which category is contributing to the overall difference.</p>
        <div className="table-wrap mt-4">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
              <tr><th className="p-3">Category</th><th className="p-3 text-right">Payslip</th><th className="p-3 text-right">Screenshots</th><th className="p-3 text-right">Difference</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {categoryRows.map((row) => (
                <tr key={row.category}>
                  <td className="p-3 font-semibold">{row.category}</td>
                  <td className="p-3 text-right tabular-nums">{decimalHoursLabel(row.payslip)}</td>
                  <td className="p-3 text-right tabular-nums">{decimalHoursLabel(row.screenshots)}</td>
                  <td className={`p-3 text-right font-bold tabular-nums ${Math.abs(row.difference) > 0.25 ? "text-red-700" : Math.abs(row.difference) > 0.05 ? "text-amber-700" : "text-emerald-700"}`}>{signedHoursWithMinutes(row.difference)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card mt-6">
        <h2 className="text-lg font-bold text-navy-950">Daily screenshot hours</h2>
        <p className="mt-1 text-sm text-slate-500">Each date includes its weekday and the hours calculated after break deductions. A category-total difference is shown beside that category's last day; it does not mean that day alone caused the difference.</p>
        <div className="table-wrap mt-4">
          <table className="w-full min-w-[940px] text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
              <tr><th className="p-3">Date</th><th className="p-3">Day</th><th className="p-3">Category</th><th className="p-3">Start</th><th className="p-3">Finish</th><th className="p-3 text-right">Break</th><th className="p-3 text-right">Hours</th><th className="p-3 text-right">Category comparison</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {dailyRows.map((shift, index) => (
                <tr key={shift.id ?? `${shift.shift_date}-${shift.start_time}`}>
                  <td className="p-3">{dateLabel(shift.shift_date)}</td>
                  <td className="p-3 font-medium">{weekdayLabel(shift.shift_date)}</td>
                  <td className="p-3">{shift.category}</td>
                  <td className="p-3 tabular-nums">{shift.start_time?.slice(0, 5) ?? "—"}</td>
                  <td className="p-3 tabular-nums">{shift.finish_time?.slice(0, 5) ?? "—"}</td>
                  <td className="p-3 text-right tabular-nums">{shift.unpaid_break_minutes} min</td>
                  <td className="p-3 whitespace-nowrap text-right font-bold tabular-nums">{decimalHoursLabel(shift.total_worked_hours)}</td>
                  <td className="p-3 text-right">
                    {lastRowForCategory.get(shift.category) === index ? (
                      <span title="Combined payslip-versus-screenshot difference for this category, shown on its last listed day." className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${
                        Math.abs(categoryDifference.get(shift.category) ?? 0) > 0.25
                          ? "bg-red-50 text-red-700"
                          : Math.abs(categoryDifference.get(shift.category) ?? 0) > 0.05
                            ? "bg-amber-50 text-amber-700"
                            : "bg-emerald-50 text-emerald-700"
                      }`}>
                        {shift.category} total: {signedHoursWithMinutes(categoryDifference.get(shift.category) ?? 0)}
                      </span>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-200 bg-slate-50">
                <th className="p-3 text-right text-sm" colSpan={7}>Pay-period total difference (screenshots − payslip)</th>
                <td className={`p-3 text-right font-bold tabular-nums ${
                  result.hours_state === "matching"
                    ? "text-emerald-700"
                    : result.hours_state === "warning"
                      ? "text-amber-700"
                      : "text-red-700"
                }`}>{signedHoursWithMinutes(Number(result.hours_difference))}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
      <section className="card mt-6">
        <h2 className="text-lg font-bold text-navy-950">Validation review</h2>
        <div className="mt-4"><Warnings warnings={period.warnings} /></div>
      </section>
      {actionError && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700" role="alert">{actionError}</p>}
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button className="btn-secondary" disabled={working} onClick={() => navigate(`/pay-periods/${period.id}/shifts`)}><Pencil size={18} /> Edit shifts</button>
        {period.status === "confirmed" && <button className="btn-secondary" disabled={working} onClick={exportOne}><Download size={19} /> Export this record</button>}
        {period.status !== "confirmed" && <button className="btn-primary" disabled={working} onClick={confirm}><Check size={19} /> {working ? "Confirming…" : "Confirm and save record"}</button>}
      </div>
    </>
  );
}

function EstimatedPayCard({ result }: { result: PayPeriod["reconciliation"] }) {
  const difference = Number(result.estimated_pay_difference);
  const direction = result.estimated_pay_direction;
  const presentation = direction === "potentially_below"
    ? {
        label: "Potentially paid below estimate",
        Icon: TrendingDown,
        tone: "border-red-200 bg-red-50 text-red-800",
      }
    : direction === "potentially_above"
      ? {
          label: "Potentially paid above estimate",
          Icon: TrendingUp,
          tone: "border-blue-200 bg-blue-50 text-blue-800",
        }
      : direction === "approximately_matching"
        ? {
            label: "Approximately matches estimate",
            Icon: CircleCheck,
            tone: "border-emerald-200 bg-emerald-50 text-emerald-800",
          }
        : {
            label: "Incomplete pay estimate",
            Icon: TriangleAlert,
            tone: "border-amber-200 bg-amber-50 text-amber-800",
          };
  const DirectionIcon = presentation.Icon;

  return (
    <section className="card mt-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-navy-950">
            <Calculator size={20} /> Estimated pay from worked hours
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Screenshot hours × the matching payslip rate for each pay category.
          </p>
        </div>
        <span className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-bold ${presentation.tone}`}>
          <DirectionIcon size={17} /> {presentation.label}
        </span>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <Metric label="Estimated earnings" value={aud(result.estimated_pay_from_shifts)} />
        <Metric label="Paid compared earnings" value={aud(result.paid_compared_earnings)} />
        <Metric
          label="Paid − estimate"
          value={result.estimated_pay_complete ? signedAud(difference) : "Incomplete"}
        />
      </div>

      <p className={`mt-4 rounded-xl border p-3 text-sm font-medium ${presentation.tone}`}>
        {result.estimated_pay_message}
      </p>

      <div className="table-wrap mt-5">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
            <tr>
              <th className="p-3">Category</th>
              <th className="p-3 text-right">Screenshot hours</th>
              <th className="p-3 text-right">Payslip rate</th>
              <th className="p-3 text-right">Estimated</th>
              <th className="p-3 text-right">Paid</th>
              <th className="p-3 text-right">Paid − estimate</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.category_pay_comparison.map((row) => (
              <tr key={row.category}>
                <td className="p-3 font-semibold">{row.category}</td>
                <td className="p-3 text-right tabular-nums">{decimalHoursLabel(row.screenshot_hours)}</td>
                <td className="p-3 text-right tabular-nums">{optionalAud(row.hourly_rate)}</td>
                <td className="p-3 text-right tabular-nums">{optionalAud(row.estimated_pay)}</td>
                <td className="p-3 text-right tabular-nums">{optionalAud(row.paid_amount)}</td>
                <td className="p-3 text-right font-bold tabular-nums">
                  {row.difference === null ? "Needs rate" : signedAud(Number(row.difference))}
                </td>
              </tr>
            ))}
            {!result.category_pay_comparison.length && (
              <tr>
                <td className="p-5 text-center text-slate-500" colSpan={6}>
                  Add and verify shift hours and payslip rates to calculate this estimate.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs leading-5 text-slate-500">
        Estimate only. It does not account for award interpretation, minimum engagements,
        overtime rules, allowances, leave, tax, superannuation or payroll adjustments.
        It does not determine a legal overpayment or underpayment.
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-bold tabular-nums text-navy-950">{value}</p>
    </div>
  );
}

function optionalAud(value: string | null): string {
  return value === null ? "Not available" : aud(value);
}

function signedAud(value: number): string {
  const safe = Math.abs(value) < 0.005 ? 0 : value;
  return `${safe > 0 ? "+" : safe < 0 ? "−" : ""}${aud(Math.abs(safe))}`;
}

function hoursByCategory(period: PayPeriod) {
  const payslip = new Map<string, number>();
  const screenshots = new Map<string, number>();
  for (const item of period.payslip.items) {
    if (item.hours !== null) payslip.set(item.category, (payslip.get(item.category) ?? 0) + Number(item.hours));
  }
  for (const shift of period.shifts) {
    screenshots.set(shift.category, (screenshots.get(shift.category) ?? 0) + Number(shift.total_worked_hours ?? 0));
  }
  return [...new Set([...payslip.keys(), ...screenshots.keys()])]
    .sort()
    .map((category) => {
      const paid = payslip.get(category) ?? 0;
      const worked = screenshots.get(category) ?? 0;
      return { category, payslip: paid, screenshots: worked, difference: worked - paid };
    });
}

function signedHours(value: number): string {
  const rounded = Math.abs(value) < 0.005 ? 0 : value;
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(2)} h`;
}

function signedHoursWithMinutes(value: number): string {
  return `${signedHours(value)} (${value > 0 ? "+" : ""}${hoursAndMinutes(value)})`;
}

function ComparisonCard({ title, rows, state }: { title: string; rows: string[][]; state: string }) {
  const stateStyle = state === "matching" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : state === "warning" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200";
  return (
    <section className="card">
      <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-lg font-bold text-navy-950"><Scale size={20} /> {title}</h2><span className={`rounded-full border px-2.5 py-1 text-xs font-bold uppercase ${stateStyle}`}>{state}</span></div>
      <dl className="mt-5 divide-y divide-slate-100">{rows.map(([label, value]) => <div className="flex justify-between gap-3 py-3" key={label}><dt className="text-slate-600">{label}</dt><dd className="font-bold tabular-nums text-navy-950">{value}</dd></div>)}</dl>
    </section>
  );
}
