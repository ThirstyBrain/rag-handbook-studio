/** Structured, level-filtered console logging. One place to swap in a real sink later. */
type Level = "debug" | "info" | "warn" | "error";
const ORDER: Record<Level, number> = { debug: 0, info: 1, warn: 2, error: 3 };
const threshold: Level = import.meta.env.DEV ? "debug" : "warn";

function emit(level: Level, scope: string, message: string, data?: unknown) {
  if (ORDER[level] < ORDER[threshold]) return;
  const line = `[${scope}] ${message}`;
  (level === "debug" ? console.debug : console[level])(line, ...(data === undefined ? [] : [data]));
}

export function createLogger(scope: string) {
  return {
    debug: (m: string, d?: unknown) => emit("debug", scope, m, d),
    info: (m: string, d?: unknown) => emit("info", scope, m, d),
    warn: (m: string, d?: unknown) => emit("warn", scope, m, d),
    error: (m: string, d?: unknown) => emit("error", scope, m, d),
  };
}
