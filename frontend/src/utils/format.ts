import type { ShiftPunch } from "../types";

export function aud(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0);
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(Number.isFinite(numeric) ? numeric : 0);
}

export function dateLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

export function weekdayLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "long",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

export function hoursAndMinutes(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0);
  const safe = Number.isFinite(numeric) ? numeric : 0;
  const totalMinutes = Math.round(Math.abs(safe) * 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${safe < 0 ? "-" : ""}${hours} h ${String(minutes).padStart(2, "0")} min`;
}

export function decimalHoursLabel(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0);
  const safe = Number.isFinite(numeric) ? numeric : 0;
  return `${safe.toFixed(2)} h (${hoursAndMinutes(safe)})`;
}

export function calculateDailyFromPunches(punches: ShiftPunch[]): {
  startTime: string | null;
  finishTime: string | null;
  breakMinutes: number;
} {
  const intervals = punches.flatMap((punch) => {
    const rawStart = timeMinutes(punch.in_time);
    const rawFinishValue = timeMinutes(punch.out_time);
    if (rawStart === null || rawFinishValue === null) return [];
    const rawFinish = rawFinishValue <= rawStart
      ? rawFinishValue + 24 * 60
      : rawFinishValue;
    let start = Math.ceil(rawStart / 15) * 15;
    let finish = Math.floor(rawFinishValue / 15) * 15;
    if (finish <= start) finish += 24 * 60;
    if (rawFinish - rawStart < 12 * 60 && finish - start > 12 * 60) {
      start = rawStart;
      finish = rawFinish;
    }
    return [{ start, finish }];
  }).sort((left, right) => left.start - right.start);

  if (!intervals.length) {
    return { startTime: null, finishTime: null, breakMinutes: 0 };
  }
  const start = intervals[0].start;
  let finish = intervals[0].finish;
  let breakMinutes = 0;
  for (const interval of intervals.slice(1)) {
    if (interval.start > finish) {
      const gap = interval.start - finish;
      breakMinutes += gap < 90 ? 60 : 120;
    }
    finish = Math.max(finish, interval.finish);
  }
  return {
    startTime: minutesTime(start),
    finishTime: minutesTime(finish),
    breakMinutes,
  };
}

export function calculateWorkedHours(
  start: string | null,
  finish: string | null,
  breakMinutes: number,
): string {
  if (!start || !finish) return "0.00";
  const [startHour, startMinute] = start.split(":").map(Number);
  const [finishHour, finishMinute] = finish.split(":").map(Number);
  let minutes = finishHour * 60 + finishMinute - (startHour * 60 + startMinute);
  if (minutes <= 0) minutes += 24 * 60;
  minutes = Math.max(0, minutes - (Number(breakMinutes) || 0));
  return (minutes / 60).toFixed(2);
}

function timeMinutes(value: string | null): number | null {
  if (!value) return null;
  const [hours, minutes] = value.split(":").map(Number);
  if (!Number.isInteger(hours) || !Number.isInteger(minutes)) return null;
  return hours * 60 + minutes;
}

function minutesTime(value: number): string {
  const dayMinutes = ((value % (24 * 60)) + 24 * 60) % (24 * 60);
  return `${String(Math.floor(dayMinutes / 60)).padStart(2, "0")}:${String(dayMinutes % 60).padStart(2, "0")}`;
}
