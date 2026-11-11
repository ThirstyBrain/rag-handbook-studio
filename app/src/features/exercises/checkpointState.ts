import { useCallback, useState } from "react";
import { slugify } from "@/content/parse/text";
import { readJson, writeJson } from "@/shared/storage/storage";

/**
 * Which checkpoint questions the reader has marked done, on this device. Keys combine the chapter
 * number with a slug of the question text, so editing one question in the handbook resets only it.
 */
const KEY = "checkpoint-done";

export const questionKey = (chapter: number, text: string) => `${chapter}:${slugify(text).slice(0, 60)}`;

export function useCheckpointProgress() {
  const [done, setDone] = useState<Record<string, true>>(() => readJson<Record<string, true>>(KEY, {}));
  const toggle = useCallback((key: string) => {
    setDone((prev) => {
      const next = { ...prev };
      if (next[key]) delete next[key];
      else next[key] = true;
      writeJson(KEY, next);
      return next;
    });
  }, []);
  return { done, toggle };
}
