/**
 * The hero's environment: ivory light from the upper left, azure from the upper right, and deep
 * navy rising from the bottom in layered teal waves over a fine technical grid. One SVG, scaled
 * to the section; the waves drift very slowly (disabled under reduced motion).
 */
export function HeroBackdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="backdrop__grid" />
      <svg className="backdrop__waves" viewBox="0 0 1440 1000" preserveAspectRatio="none">
        <defs>
          <linearGradient id="bd-deep" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0b2a45" />
            <stop offset="0.55" stopColor="#06182c" />
            <stop offset="1" stopColor="#031020" />
          </linearGradient>
          <linearGradient id="bd-teal" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#00a6a6" stopOpacity="0.8" />
            <stop offset="0.5" stopColor="#0f6f86" stopOpacity="0.75" />
            <stop offset="1" stopColor="#6fafe5" stopOpacity="0.3" />
          </linearGradient>
          <linearGradient id="bd-mist" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
            <stop offset="0.6" stopColor="#bfe3ee" stopOpacity="0.75" />
            <stop offset="1" stopColor="#6fafe5" stopOpacity="0.35" />
          </linearGradient>
        </defs>
        <path className="backdrop__mist" d="M520 1000 C 700 760, 900 520, 1150 360 S 1400 210, 1440 190 L1440 1000Z" fill="url(#bd-mist)" />
        <path className="backdrop__teal" d="M640 1000 C 820 820, 980 640, 1180 520 S 1400 420, 1440 400 L1440 1000Z" fill="url(#bd-teal)" />
        <path d="M0 830 C 260 780, 520 860, 760 840 S 1180 700, 1440 600 L1440 1000 L0 1000Z" fill="url(#bd-deep)" />
        <g className="backdrop__lines" fill="none" stroke="#31d4e5" strokeOpacity="0.32" strokeWidth="1">
          <path d="M0 812 C 260 762, 520 842, 760 822 S 1180 682, 1440 582" />
          <path d="M600 1000 C 790 800, 960 610, 1170 490 S 1400 380, 1440 370" strokeOpacity="0.22" />
          <path d="M0 870 C 300 830, 560 900, 820 880 S 1220 760, 1440 680" strokeOpacity="0.14" />
        </g>
      </svg>
      <div className="backdrop__glow" />
    </div>
  );
}
