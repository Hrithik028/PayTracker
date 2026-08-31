import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { PayPeriod } from "../types";

export function usePayPeriod(id?: string) {
  const [period, setPeriod] = useState<PayPeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      setPeriod(await api.getPeriod(id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load pay period");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);
  return { period, setPeriod, loading, error, reload: load };
}

