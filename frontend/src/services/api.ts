import type { DashboardData, PayPeriod, PayPeriodSummary } from "../types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : Array.isArray(payload.detail)
        ? payload.detail
          .map((issue: { loc?: Array<string | number>; msg?: string }) => {
            const field = issue.loc?.filter((part) => part !== "body").join(".");
            return `${field ? `${field}: ` : ""}${issue.msg ?? "Invalid value"}`;
          })
          .join("; ")
        : payload.detail?.message ?? `Request failed with HTTP ${response.status}`;
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  dashboard: () => request<DashboardData>("/api/dashboard"),
  listPeriods: () => request<PayPeriodSummary[]>("/api/pay-periods"),
  getPeriod: (id: string) => request<PayPeriod>(`/api/pay-periods/${id}`),
  createPeriod: (body: unknown) => request<PayPeriod>("/api/pay-periods", json("POST", body)),
  updatePeriod: (id: string, body: unknown) =>
    request<PayPeriod>(`/api/pay-periods/${id}`, json("PUT", body)),
  confirmPeriod: (id: string) =>
    request<PayPeriod>(`/api/pay-periods/${id}/confirm`, { method: "POST" }),
  deletePeriod: (id: string) =>
    request<{ deleted: boolean }>(`/api/pay-periods/${id}`, { method: "DELETE" }),
  processFiles: (form: FormData) =>
    request<PayPeriod>("/api/process", { method: "POST", body: form }),
  export: (periodId?: string) =>
    request<{ id: string; filename: string; download_url: string }>(
      `/api/exports${periodId ? `?period_id=${encodeURIComponent(periodId)}` : ""}`,
      { method: "POST" },
    ),
  getSettings: () => request<Record<string, string | number | boolean>>("/api/settings"),
  updateSettings: (body: unknown) =>
    request<Record<string, string | number | boolean>>("/api/settings", json("PUT", body)),
};

export function updatePayload(period: PayPeriod) {
  return {
    employer_name: period.employer_name,
    start_date: period.start_date,
    end_date: period.end_date,
    payslip: {
      employee_name: period.payslip.employee_name,
      payment_date: period.payslip.payment_date,
      gross_pay: period.payslip.gross_pay,
      net_pay: period.payslip.net_pay,
      tax_withheld: period.payslip.tax_withheld,
      superannuation: period.payslip.superannuation,
      total_paid_hours: period.payslip.total_paid_hours,
      deductions: period.payslip.deductions,
      allowances: period.payslip.allowances,
      notes: period.payslip.notes,
      verified: period.payslip.verified,
      items: period.payslip.items,
    },
    shifts: period.shifts,
  };
}
