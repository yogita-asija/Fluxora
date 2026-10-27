import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../api/client.js";

// Minimal data-fetching hook: { data, error, loading, reload }.
export function useFetch(request) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true }));
    try {
      const response = await request();
      setState({ data: response.data, error: null, loading: false });
    } catch (err) {
      setState({ data: null, error: errorMessage(err), loading: false });
    }
  }, [request]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
