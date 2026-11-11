import { createLogger } from "../logging/log";
const log = createLogger("storage");
const PREFIX = "rag-handbook:";

/** localStorage that never throws (private windows, blocked storage). Per-viewer conveniences only. */
export function readJson<T>(key: string, fallback: T): T {
  try {
    const v = window.localStorage.getItem(PREFIX + key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch (e) {
    log.warn(`read failed for ${key}`, e);
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch (e) {
    log.warn(`write failed for ${key}`, e);
  }
}
