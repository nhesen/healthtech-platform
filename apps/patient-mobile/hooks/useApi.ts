import { useCallback, useEffect, useState } from "react";

export function useApi<T>(loader: () => Promise<T>, dependencies: unknown[] = [], intervalMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try { setError(""); setData(await loader()); }
    catch (value) { setError(value instanceof Error ? value.message : "Unable to load this information."); }
    finally { setLoading(false); }
  }, dependencies);
  useEffect(() => {
    void reload();
    if (!intervalMs) return;
    const timer = setInterval(() => void reload(), intervalMs);
    return () => clearInterval(timer);
  }, [reload, intervalMs]);
  return { data, error, loading, reload, setData };
}
