import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "orderflow-theme";

export function useTheme() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
    } catch {
      /* storage unavailable: theme just won't persist */
    }
  }, [dark]);

  const toggle = useCallback(() => setDark((value) => !value), []);
  return { dark, toggle };
}
