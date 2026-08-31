export type Status = "draft" | "needs_review" | "confirmed";

export interface PayItem {
  id?: string;
  category: string;
  description: string;
  hours: string | null;
  hourly_rate: string | null;
  amount: string | null;
  confidence_score: number;
  source_text?: string | null;
  verified: boolean;
}

export interface ShiftPunch {
  id?: string;
  sequence: number;
  in_time: string | null;
  out_time: string | null;
  confidence_score: number;
  verified: boolean;
}

export interface Shift {
  id?: string;
  source_screenshot_id?: string | null;
  shift_date: string | null;
  start_time: string | null;
  finish_time: string | null;
  unpaid_break_minutes: number;
  total_worked_hours: string | null;
  category: string;
  confidence_score: number;
  verified: boolean;
  punches: ShiftPunch[];
}

export interface Warning {
  code: string;
  message: string;
  field?: string | null;
  state: "warning" | "discrepancy";
}

export interface CategoryPayComparison {
  category: string;
  screenshot_hours: string;
  hourly_rate: string | null;
  estimated_pay: string | null;
  paid_amount: string | null;
  difference: string | null;
}

export interface PayPeriod {
  id: string;
  employer_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: Status;
  confirmed_at: string | null;
  payslip: {
    id: string | null;
    original_filename: string | null;
    preview_url: string | null;
    employee_name: string | null;
    payment_date: string | null;
    gross_pay: string | null;
    net_pay: string | null;
    tax_withheld: string | null;
    superannuation: string | null;
    total_paid_hours: string | null;
    deductions: string | null;
    allowances: string | null;
    notes: string | null;
    field_confidence: Record<string, number>;
    verified: boolean;
    items: PayItem[];
  };
  shifts: Shift[];
  screenshots: Array<{ id: string; original_filename: string | null; preview_url: string }>;
  warnings: Warning[];
  reconciliation: {
    payslip_hours: string;
    screenshot_hours: string;
    hours_difference: string;
    hours_state: string;
    calculated_amount: string;
    paid_line_item_amount: string;
    amount_difference: string;
    amount_state: string;
    estimated_pay_from_shifts: string;
    paid_compared_earnings: string;
    estimated_pay_difference: string;
    estimated_pay_direction:
      | "potentially_above"
      | "potentially_below"
      | "approximately_matching"
      | "unavailable";
    estimated_pay_state: string;
    estimated_pay_complete: boolean;
    estimated_pay_message: string;
    category_pay_comparison: CategoryPayComparison[];
    label: string;
  };
  created_at: string;
  updated_at: string;
}

export interface PayPeriodSummary {
  id: string;
  employer_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: Status;
  gross_pay: string | null;
  net_pay: string | null;
  total_paid_hours: string | null;
  screenshot_hours: string;
  updated_at: string;
}

export interface DashboardData {
  totals: {
    gross_pay: string;
    net_pay: string;
    tax_withheld: string;
    superannuation: string;
    confirmed_hours: string;
  };
  effective_average_hourly_rate: string;
  unresolved_discrepancies: number;
  monthly_earnings: Array<{ month: string; gross_pay: string }>;
  recent_pay_periods: PayPeriodSummary[];
}
