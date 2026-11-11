/**
 * The mark: on a midnight-navy tile, a teal-to-cyan stroke for the keyword leg and an azure stroke
 * for the semantic leg converge on one fused point — the hybrid retrieval at the centre of the book.
 */
import { useId } from "react";

export function BrandMark({ size = 32 }: { size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 44 44" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-tile`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#12304f" />
          <stop offset="1" stopColor="#06182c" />
        </linearGradient>
        <linearGradient id={`${id}-lex`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#31d4e5" />
          <stop offset="1" stopColor="#00a6a6" />
        </linearGradient>
      </defs>
      <rect width="44" height="44" rx="11" fill={`url(#${id}-tile)`} />
      <rect x="0.5" y="0.5" width="43" height="43" rx="10.5" fill="none" stroke="rgb(49 212 229 / 0.28)" />
      <path d="M10 12.5h9.5l5.5 9.5-5.5 9.5H10" fill="none" stroke={`url(#${id}-lex)`} strokeWidth="3.4" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M34 12.5h-5.2L25 22" fill="none" stroke="#6fafe5" strokeWidth="3.4" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="25" cy="22" r="3.2" fill="#ffffff" />
    </svg>
  );
}
