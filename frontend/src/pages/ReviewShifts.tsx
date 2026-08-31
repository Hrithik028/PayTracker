import { ArrowRight, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Confidence } from "../components/Confidence";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { Warnings } from "../components/Warnings";
import { usePayPeriod } from "../hooks/usePayPeriod";
import { api, updatePayload } from "../services/api";
import { navigate, payPeriodIdFromPath } from "../services/navigation";
import type { Shift, ShiftPunch } from "../types";
import { calculateDailyFromPunches, calculateWorkedHours, decimalHoursLabel, weekdayLabel } from "../utils/format";
import { Progress } from "./ReviewPayslip";

const categories = ["Ordinary", "Overtime", "Saturday", "Sunday", "Public holiday", "Leave", "Other"];

export function ReviewShifts() {
  const id = payPeriodIdFromPath();
  const { period, setPeriod, loading, error, reload } = usePayPeriod(id);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  if (loading) return <LoadingState label="Loading extracted shifts…" />;
  if (error || !period) return <ErrorState message={error || "Pay period not found"} retry={reload} />;

  const setShift = (index: number, field: keyof Shift, value: unknown) => {
    const shifts = period.shifts.map((shift, shiftIndex) => {
      if (shiftIndex !== index) return shift;
      const changed = { ...shift, [field]: value };
      changed.total_worked_hours = calculateWorkedHours(changed.start_time, changed.finish_time, changed.unpaid_break_minutes);
      return changed;
    });
    setPeriod({ ...period, shifts });
  };
  const punchesFor = (shift: Shift): ShiftPunch[] => shift.punches?.length
    ? shift.punches
    : [{
      sequence: 0,
      in_time: shift.start_time,
      out_time: shift.finish_time,
      confidence_score: shift.confidence_score,
      verified: shift.verified,
    }];
  const updatePunches = (shiftIndex: number, punches: ShiftPunch[]) => {
    const shifts = period.shifts.map((shift, index) => {
      if (index !== shiftIndex) return shift;
      const sequenced = punches.map((punch, sequence) => ({ ...punch, sequence }));
      const daily = calculateDailyFromPunches(sequenced);
      return {
        ...shift,
        punches: sequenced,
        start_time: daily.startTime,
        finish_time: daily.finishTime,
        unpaid_break_minutes: daily.breakMinutes,
        total_worked_hours: calculateWorkedHours(
          daily.startTime,
          daily.finishTime,
          daily.breakMinutes,
        ),
      };
    });
    setPeriod({ ...period, shifts });
  };
  const setPunch = (
    shiftIndex: number,
    punchIndex: number,
    field: "in_time" | "out_time",
    value: string | null,
  ) => {
    const punches = punchesFor(period.shifts[shiftIndex]).map((punch, index) =>
      index === punchIndex ? { ...punch, [field]: value, verified: false } : punch,
    );
    updatePunches(shiftIndex, punches);
  };
  const addPunch = (shiftIndex: number) => {
    const punches = punchesFor(period.shifts[shiftIndex]);
    updatePunches(shiftIndex, [
      ...punches,
      {
        sequence: punches.length,
        in_time: null,
        out_time: null,
        confidence_score: 0,
        verified: false,
      },
    ]);
  };
  const removePunch = (shiftIndex: number, punchIndex: number) => {
    const punches = punchesFor(period.shifts[shiftIndex]).filter(
      (_, index) => index !== punchIndex,
    );
    updatePunches(shiftIndex, punches.length ? punches : [{
      sequence: 0,
      in_time: null,
      out_time: null,
      confidence_score: 0,
      verified: false,
    }]);
  };
  const add = () => setPeriod({ ...period, shifts: [...period.shifts, emptyShift()] });
  const save = async () => {
    setSaving(true); setSaveError("");
    const reviewed = {
      ...period,
      shifts: period.shifts.map((shift) => ({
        ...shift,
        verified: true,
        punches: (shift.punches ?? []).map((punch) => ({ ...punch, verified: true })),
      })),
    };
    try {
      await api.updatePeriod(period.id, updatePayload(reviewed));
      navigate(`/pay-periods/${period.id}/reconciliation`);
    } catch (reason) { setSaveError(reason instanceof Error ? reason.message : "Unable to save shifts"); }
    finally { setSaving(false); }
  };

  return (
    <>
      <PageHeader title="Review shifts" description="Edit the date, start, finish, break and category. Day and worked hours recalculate automatically." />
      <Progress current={2} />
      {period.screenshots.length > 0 && (
        <section className="card mt-6">
          <h2 className="font-bold text-navy-950">Timing screenshots</h2>
          <div className="mt-4 flex gap-4 overflow-x-auto pb-2">
            {period.screenshots.map((image) => <figure className="min-w-56" key={image.id}><img className="h-72 w-56 rounded-xl border border-slate-200 object-contain" src={image.preview_url} alt={image.original_filename || "Timing screenshot"} /><figcaption className="mt-1 truncate text-xs text-slate-500">{image.original_filename}</figcaption></figure>)}
          </div>
        </section>
      )}
      <section className="card mt-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold text-navy-950">Daily shift rows</h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700"><Pencil size={13} /> Editing enabled</span>
            </div>
            <p className="text-sm text-slate-500">Multiple punch pairs on one date are combined. Clock-ins round forward and clock-outs round backward to the nearest 15-minute boundary. Between-shift gaps become a 60- or 120-minute unpaid break. Overnight finishes remain supported.</p>
          </div>
          <button className="btn-secondary" onClick={add}><Plus size={18} /> Add shift</button>
        </div>
        <div className="table-wrap mt-4">
          <table className="w-full min-w-[1280px] text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600"><tr><th className="p-3">Date</th><th className="p-3">Day</th><th className="p-3">IN / OUT punches</th><th className="p-3">Rounded shift</th><th className="p-3">Break</th><th className="p-3">Hours</th><th className="p-3">Category</th><th className="p-3">Confidence</th><th className="p-3"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {period.shifts.map((shift, index) => (
                <tr key={shift.id ?? `new-${index}`}>
                  <td className="p-2"><input aria-label={`Shift ${index + 1} date`} className="input w-40" type="date" value={shift.shift_date ?? ""} onChange={(event) => setShift(index, "shift_date", event.target.value || null)} /></td>
                  <td className="p-2 font-medium text-slate-700" title="Calculated from the selected date">{weekdayLabel(shift.shift_date)}</td>
                  <td className="p-2">
                    <div className="min-w-[310px] space-y-2">
                      {punchesFor(shift).map((punch, punchIndex) => (
                        <div className="flex items-center gap-2" key={punch.id ?? `punch-${punchIndex}`}>
                          <span className="w-7 text-xs font-bold text-amber-700">IN</span>
                          <input aria-label={`Shift ${index + 1} punch ${punchIndex + 1} in time`} className="input w-28" type="time" value={punch.in_time ?? ""} onChange={(event) => setPunch(index, punchIndex, "in_time", event.target.value || null)} />
                          <span className="w-9 text-xs font-bold text-pink-700">OUT</span>
                          <input aria-label={`Shift ${index + 1} punch ${punchIndex + 1} out time`} className="input w-28" type="time" value={punch.out_time ?? ""} onChange={(event) => setPunch(index, punchIndex, "out_time", event.target.value || null)} />
                          <button className="rounded-lg p-2 text-red-600 hover:bg-red-50" type="button" aria-label={`Remove punch pair ${punchIndex + 1}`} onClick={() => removePunch(index, punchIndex)}><Trash2 size={16} /></button>
                        </div>
                      ))}
                      <button className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-50" type="button" onClick={() => addPunch(index)}><Plus size={15} /> Add IN/OUT pair</button>
                    </div>
                  </td>
                  <td className="p-2 whitespace-nowrap font-medium tabular-nums text-slate-700"><span title="Calculated using quarter-hour rounding">{shift.start_time?.slice(0, 5) ?? "—"}–{shift.finish_time?.slice(0, 5) ?? "—"}</span></td>
                  <td className="p-2"><select className="input w-36" aria-label={`Shift ${index + 1} unpaid break`} value={shift.unpaid_break_minutes} onChange={(event) => setShift(index, "unpaid_break_minutes", Number(event.target.value))}>{![0, 60, 120].includes(shift.unpaid_break_minutes) && <option value={shift.unpaid_break_minutes}>{shift.unpaid_break_minutes} min (review)</option>}<option value={0}>No break</option><option value={60}>1 hour</option><option value={120}>2 hours</option></select></td>
                  <td className="p-2 whitespace-nowrap font-semibold tabular-nums" title="Calculated from start, finish and break">{decimalHoursLabel(calculateWorkedHours(shift.start_time, shift.finish_time, shift.unpaid_break_minutes))}</td>
                  <td className="p-2"><select aria-label={`Shift ${index + 1} category`} className="input w-40" value={shift.category} onChange={(event) => setShift(index, "category", event.target.value)}>{categories.map((category) => <option key={category}>{category}</option>)}</select></td>
                  <td className="p-2"><Confidence value={shift.confidence_score} /></td>
                  <td className="p-2"><button className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label="Delete shift" onClick={() => setPeriod({ ...period, shifts: period.shifts.filter((_, itemIndex) => itemIndex !== index) })}><Trash2 size={18} /></button></td>
                </tr>
              ))}
              {!period.shifts.length && <tr><td colSpan={9} className="p-8 text-center text-slate-500">No shifts were extracted. Add shifts manually from the screenshots.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="mt-5"><Warnings warnings={period.warnings.filter((item) => item.code.includes("shift") || item.code.includes("overlap"))} /></div>
      </section>
      {saveError && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700" role="alert">{saveError}</p>}
      <div className="mt-6 flex justify-end"><button className="btn-primary w-full sm:w-auto" disabled={saving} onClick={save}><Save size={19} /> {saving ? "Saving…" : "Save edited shifts & reconcile"} <ArrowRight size={18} /></button></div>
    </>
  );
}

function emptyShift(): Shift {
  return {
    shift_date: null,
    start_time: null,
    finish_time: null,
    unpaid_break_minutes: 0,
    total_worked_hours: "0.00",
    category: "Ordinary",
    confidence_score: 0,
    verified: false,
    punches: [{
      sequence: 0,
      in_time: null,
      out_time: null,
      confidence_score: 0,
      verified: false,
    }],
  };
}
