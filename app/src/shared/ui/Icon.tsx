import type { SVGProps } from "react";

/**
 * A small, consistent line-icon set (24px grid, 1.7 stroke, round joins). Paths are original.
 * Icons are decorative by default; pass `title` to make one meaningful to assistive tech.
 */
const PATHS = {
  home: "M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5h-5v5H5a1 1 0 0 1-1-1z",
  book: "M4 5.5C4 4.7 4.7 4 5.5 4H11v15.5H5.5A1.5 1.5 0 0 1 4 18zM20 5.5c0-.8-.7-1.5-1.5-1.5H13v15.5h5.5c.8 0 1.5-.7 1.5-1.5z",
  network: "M12 4.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM5 15.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM19 15.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM12 8.5v3.5M12 12l-5.6 4M12 12l5.6 4",
  shield: "M12 3.5 19 6v5.5c0 4.2-3 7.6-7 9-4-1.4-7-4.8-7-9V6zM8.8 12l2.2 2.2 4.2-4.4",
  compass: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM15.3 8.7l-1.9 4.7-4.7 1.9 1.9-4.7z",
  flask: "M9.5 3.5h5M10.5 3.5v5.2L5.4 17.4A2 2 0 0 0 7.1 20.5h9.8a2 2 0 0 0 1.7-3.1l-5.1-8.7V3.5M7.8 14h8.4",
  terminal: "M4.5 5h15a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM7.5 9.5l3 2.5-3 2.5M12.5 15h4",
  search: "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM15.3 15.3 20 20",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  play: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM10.2 8.8v6.4l5.2-3.2z",
  file: "M7 3.5h7l4.5 4.5v11.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1zM14 3.5V8h4.5M9 12h6M9 15.5h6",
  gear: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 3.5v2.2M12 18.3v2.2M20.5 12h-2.2M5.7 12H3.5M18 6l-1.6 1.6M7.6 16.4 6 18M18 18l-1.6-1.6M7.6 7.6 6 6",
  cubes: "M12 3.8 15.8 6v4.3L12 12.5 8.2 10.3V6zM7.8 11.2l3.8 2.2v4.3l-3.8 2.2L4 17.7v-4.3zM16.2 11.2l3.8 2.2v4.3l-3.8 2.2-3.8-2.2v-4.3z",
  embed: "M12 10.2a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zM12 4v4M12 16v4M4.6 8l3.5 2M15.9 14l3.5 2M4.6 16l3.5-2M15.9 10l3.5-2",
  star: "m12 4 2.4 5 5.4.7-4 3.8 1 5.4L12 16.3 7.2 18.9l1-5.4-4-3.8 5.4-.7z",
  bolt: "M13 3.5 5.5 13.5H12l-1 7 7.5-10H12z",
  check: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8.4 12.2l2.5 2.5 4.8-5",
  layers: "m12 4 8.5 4.3L12 12.6 3.5 8.3zM3.5 12.2 12 16.5l8.5-4.3M3.5 16 12 20.3l8.5-4.3",
  code: "M8.5 8 4.5 12l4 4M15.5 8l4 4-4 4M13.5 5.5l-3 13",
  chart: "M4.5 19.5h15M7 16v-4M11 16V9M15 16v-6M19 16V6.5M6.5 9.5 11 6l3.5 2.5L19 4.5",
  users: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3.5 19c.6-3 2.8-5 5.5-5s4.9 2 5.5 5M16 10.5a2.5 2.5 0 1 0 0-5M17 14c2 .4 3.3 2.1 3.6 4.5",
  menu: "M4 7h16M4 12h16M4 17h16",
} as const;

export type IconName = keyof typeof PATHS;

interface Props extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
  title?: string;
}

export function Icon({ name, size = 18, title, strokeWidth = 1.7, ...rest }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      focusable="false"
      {...rest}
    >
      {title && <title>{title}</title>}
      <path d={PATHS[name]} />
    </svg>
  );
}
