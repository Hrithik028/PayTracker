import { describe, expect, it } from "vitest";
import { calculateDailyFromPunches, calculateWorkedHours, decimalHoursLabel, hoursAndMinutes, weekdayLabel } from "./format";

describe("calculateWorkedHours", () => {
  it("deducts an unpaid break", () => {
    expect(calculateWorkedHours("09:00", "17:30", 30)).toBe("8.00");
  });

  it("supports shifts finishing after midnight", () => {
    expect(calculateWorkedHours("22:00", "06:30", 30)).toBe("8.00");
  });

  it("does not return negative hours", () => {
    expect(calculateWorkedHours("09:00", "09:30", 60)).toBe("0.00");
  });

  it("displays the weekday without a timezone date shift", () => {
    expect(weekdayLabel("2026-06-03")).toBe("Wednesday");
    expect(weekdayLabel("2026-06-06")).toBe("Saturday");
  });

  it("converts decimal hours into hours and minutes", () => {
    expect(hoursAndMinutes("7.75")).toBe("7 h 45 min");
    expect(hoursAndMinutes("-1.63")).toBe("-1 h 38 min");
    expect(decimalHoursLabel("8.50")).toBe("8.50 h (8 h 30 min)");
  });

  it("recalculates a daily shift from editable punch pairs", () => {
    expect(calculateDailyFromPunches([
      { sequence: 0, in_time: "10:56", out_time: "14:01", confidence_score: 90, verified: false },
      { sequence: 1, in_time: "15:57", out_time: "20:45", confidence_score: 90, verified: false },
    ])).toEqual({
      startTime: "11:00",
      finishTime: "20:45",
      breakMinutes: 120,
    });
  });
});
