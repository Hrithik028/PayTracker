import { ArrowRight, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Confidence } from "../components/Confidence";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { Warnings } from "../components/Warnings";
import { usePayPeriod } from "../hooks/usePayPeriod";
import { api, updatePayload } from "../services/api";
import { navigate, payPeriodIdFromPath } from "../services/navigation";
import type { PayItem, PayPeriod } from "../types";

const categories = ["Ordinary", "Overtime", "Saturday", "Sunday", "Public holiday", "Leave", "Allowance", "Bonus", "Deduction", "Other"];
const moneyFields = [
  ["gross_pay", "Gross pay"],
  ["net_pay", "Net pay"],
  ["tax_withheld", "Tax withheld"],
  ["superannuation", "Superannuation"],
  ["deductions", "Deductions"],
  ["allowances", "Allowances"],
] as const;

export function ReviewPayslip() {
  const id = payPeriodIdFromPath();
  const { period, setPeriod, loading, error, reload } = usePayPeriod(id);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  if (loading) return <LoadingState label="Loading extracted payslip…" />;
  if (error || !period) return <ErrorState message={error || "Pay period not found"} retry={reload} />;
  const setTop = (field: keyof PayPeriod, value: unknown) => setPeriod({ ...period, [field]: value });
  const setPayslip = (field: keyof PayPeriod["payslip"], value: unknown) =>
    setPeriod({ ...period, payslip: { ...period.payslip, [field]: value } });
  const setItem = (index: number, field: keyof PayItem, value: unknown) => {
    const items = period.payslip.items.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item);
    setPayslip("items", items);
  };
  const save = async () => {
    setSaving(true); setSaveError("");
    const reviewed: PayPeriod = {
      ...period,
      payslip: {
        ...period.payslip,
        verified: true,
        items: period.payslip.items.map((item) => ({ ...item, verified: true })),
      },
    };
    try {
      await api.updatePeriod(period.id, updatePayload(reviewed));
      navigate(`/pay-periods/${period.id}/shifts`);
    } catch (reason) { setSaveError(reason instanceof Error ? reason.message : "Unable to save review"); }
    finally { setSaving(false); }
  };
  const addItem = () => setPayslip("items", [...period.payslip.items, emptyItem()]);

  return (
    <>
      <PageHeader title="Review payslip" description="Check every extracted value. Low-confidence fields need particular attention." />
      <Progress current={1} />
      <div className="mt-6 grid gap-6 xl:grid-cols-[0.85fr_1.5fr]">
        <section className="card xl:sticky xl:top-6 xl:self-start">
          <h2 className="font-bold text-navy-950">Original payslip</h2>
          <p className="mt-1 truncate text-sm text-slate-500">{period.payslip.original_filename || "Manual entry"}</p>
          {period.payslip.preview_url ? (
            period.payslip.original_filename?.toLowerCase().endsWith(".pdf")
              ? <iframe className="mt-4 h-[520px] w-full rounded-xl border border-slate-200" title="Original payslip preview" src={period.payslip.preview_url} />
              : <img className="mt-4 max-h-[520px] w-full rounded-xl border border-slate-200 object-contain" alt="Original payslip" src={period.payslip.preview_url} />
          ) : <div className="mt-4 grid h-64 place-items-center rounded-xl bg-slate-100 text-sm text-slate-500">No uploaded preview</div>}
        </section>
        <div className="space-y-6">
          <section className="card">
            <h2 className="text-lg font-bold text-navy-950">Employer and dates</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Employer name" confidence={period.payslip.field_confidence.employer_name}>
                <input className="input" value={period.employer_name ?? ""} onChange={(event) => setTop("employer_name", event.target.value)} />
              </Field>
              <Field label="Employee name" confidence={period.payslip.field_confidence.employee_name}>
                <input className="input" value={period.payslip.employee_name ?? ""} onChange={(event) => setPayslip("employee_name", event.target.value)} />
              </Field>
              <Field label="Pay-period start" confidence={period.payslip.field_confidence.pay_period_start}>
                <input type="date" className="input" value={period.start_date ?? ""} onChange={(event) => setTop("start_date", event.target.value || null)} />
              </Field>
              <Field label="Pay-period end" confidence={period.payslip.field_confidence.pay_period_end}>
                <input type="date" className="input" value={period.end_date ?? ""} onChange={(event) => setTop("end_date", event.target.value || null)} />
              </Field>
              <Field label="Payment date" confidence={period.payslip.field_confidence.payment_date}>
                <input type="date" className="input" value={period.payslip.payment_date ?? ""} onChange={(event) => setPayslip("payment_date", event.target.value || null)} />
              </Field>
            </div>
          </section>
          <section className="card">
            <h2 className="text-lg font-bold text-navy-950">Pay totals</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {moneyFields.map(([field, label]) => (
                <Field key={field} label={label} confidence={period.payslip.field_confidence[field]}>
                  <MoneyInput value={period.payslip[field]} onChange={(value) => setPayslip(field, value)} />
                </Field>
              ))}
              <Field label="Total paid hours" confidence={period.payslip.field_confidence.total_paid_hours}>
                <input type="number" min="0" step="0.01" className="input" value={period.payslip.total_paid_hours ?? ""} onChange={(event) => setPayslip("total_paid_hours", event.target.value || null)} />
              </Field>
            </div>
          </section>
          <section className="card">
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="text-lg font-bold text-navy-950">Pay line items</h2><p className="text-sm text-slate-500">Hours, rate and amount are never silently changed.</p></div>
              <button className="btn-secondary" onClick={addItem}><Plus size={18} /> Add row</button>
            </div>
            <div className="table-wrap mt-4">
              <table className="min-w-[960px] w-full text-left text-sm">
                <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600"><tr>
                  <th className="p-3">Category</th><th className="p-3">Description</th><th className="p-3">Hours</th><th className="p-3">Rate</th><th className="p-3">Amount</th><th className="p-3">Confidence</th><th className="p-3"><span className="sr-only">Actions</span></th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {period.payslip.items.map((item, index) => (
                    <tr key={item.id ?? `new-${index}`}>
                      <td className="p-2"><select className="input" value={item.category} onChange={(event) => setItem(index, "category", event.target.value)}>{categories.map((category) => <option key={category}>{category}</option>)}</select></td>
                      <td className="p-2"><input className="input min-w-48" value={item.description} onChange={(event) => setItem(index, "description", event.target.value)} /></td>
                      <td className="p-2"><input type="number" min="0" step="0.01" className="input w-24" value={item.hours ?? ""} onChange={(event) => setItem(index, "hours", event.target.value || null)} /></td>
                      <td className="p-2"><input type="number" min="0" step="0.0001" className="input w-28" value={item.hourly_rate ?? ""} onChange={(event) => setItem(index, "hourly_rate", event.target.value || null)} /></td>
                      <td className="p-2"><input type="number" step="0.01" className="input w-28" value={item.amount ?? ""} onChange={(event) => setItem(index, "amount", event.target.value || null)} /></td>
                      <td className="p-2"><Confidence value={item.confidence_score} /></td>
                      <td className="p-2"><button className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label={`Delete ${item.description || "row"}`} onClick={() => setPayslip("items", period.payslip.items.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={18} /></button></td>
                    </tr>
                  ))}
                  {!period.payslip.items.length && <tr><td colSpan={7} className="p-8 text-center text-slate-500">No line items were extracted. Add rows manually.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card">
            <label className="label" htmlFor="notes">Notes</label>
            <textarea id="notes" rows={3} className="input" value={period.payslip.notes ?? ""} onChange={(event) => setPayslip("notes", event.target.value)} />
            <div className="mt-5"><Warnings warnings={period.warnings} /></div>
          </section>
          {saveError && <p className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700" role="alert">{saveError}</p>}
          <div className="flex justify-end">
            <button className="btn-primary w-full sm:w-auto" disabled={saving} onClick={save}><Save size={19} /> {saving ? "Saving…" : "Confirm payslip & review shifts"} <ArrowRight size={18} /></button>
          </div>
        </div>
      </div>
    </>
  );
}

function Field({ label, confidence, children }: { label: string; confidence?: number; children: React.ReactNode }) {
  return <label><span className="mb-1.5 flex items-center justify-between gap-2 text-sm font-semibold text-slate-700"><span>{label}</span>{confidence !== undefined && <Confidence value={confidence} />}</span>{children}</label>;
}

function MoneyInput({ value, onChange }: { value: string | null; onChange: (value: string | null) => void }) {
  return <div className="relative"><span className="pointer-events-none absolute left-3 top-2.5 text-slate-500">$</span><input type="number" step="0.01" className="input pl-7" value={value ?? ""} onChange={(event) => onChange(event.target.value || null)} /></div>;
}

function emptyItem(): PayItem {
  return { category: "Ordinary", description: "", hours: null, hourly_rate: null, amount: null, confidence_score: 0, source_text: null, verified: false };
}

export function Progress({ current }: { current: number }) {
  const steps = ["Payslip", "Shifts", "Reconciliation"];
  return <ol className="flex items-center gap-2" aria-label="Review progress">{steps.map((step, index) => <li className={`flex flex-1 items-center gap-2 text-xs font-semibold sm:text-sm ${index + 1 <= current ? "text-blue-700" : "text-slate-400"}`} key={step}><span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${index + 1 <= current ? "bg-blue-600 text-white" : "bg-slate-200 text-slate-500"}`}>{index + 1}</span><span className="hidden sm:inline">{step}</span>{index < steps.length - 1 && <span className={`h-0.5 flex-1 ${index + 1 < current ? "bg-blue-500" : "bg-slate-200"}`} />}</li>)}</ol>;
}
