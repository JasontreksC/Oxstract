import { useEffect, useState } from "react";

/** 값이 `delay` ms 동안 그대로일 때만 바뀐다. */
export function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const handle = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(handle);
  }, [value, delay]);
  return settled;
}
