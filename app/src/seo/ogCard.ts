import { deflateSync } from "node:zlib";

/**
 * Social share cards (1200x630 PNG) drawn without any image library: a tiny 5x7 bitmap font scaled up,
 * written out with Node's built-in zlib. Plain and legible by design; it runs at build time only.
 */
export const CARD_WIDTH = 1200;
export const CARD_HEIGHT = 630;

type Rgb = [number, number, number];
const PAPER: Rgb = [244, 244, 239];
const INK: Rgb = [20, 22, 26];
const MUTED: Rgb = [96, 100, 108];
const ACCENT: Rgb = [10, 125, 90];

// Each glyph: 7 rows of 5 columns, "#" is ink.
const GLYPHS: Record<string, string[]> = {
  A: [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  B: ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
  C: [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
  D: ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
  E: ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
  F: ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
  G: [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
  H: ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  I: [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
  J: ["....#", "....#", "....#", "....#", "#...#", "#...#", ".###."],
  K: ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
  L: ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
  M: ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
  N: ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
  O: [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  P: ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
  Q: [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
  R: ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
  S: [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
  T: ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
  U: ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  V: ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
  W: ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
  X: ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
  Y: ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
  Z: ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
  "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
  "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
  "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
  "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
  "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
  "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
  "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
  "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
  "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
  "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
  ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
  ",": [".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."],
  ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
  ";": [".....", ".##..", ".##..", ".....", ".##..", "..#..", ".#..."],
  "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
  "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
  '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
  "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
  ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
  "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
  "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
  "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
  "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
  "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
  "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
  "%": ["##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"],
  "=": [".....", "#####", ".....", "#####", ".....", ".....", "....."],
};

const GLYPH_COLS = 5;
const ADVANCE_COLS = GLYPH_COLS + 1;

/** Maps typographic characters onto the supported set; anything else becomes a space. */
function normalise(text: string): string {
  return text
    .replace(/[–—−]/g, "-")
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/…/g, "...")
    .replace(/×/g, "X")
    .toUpperCase();
}

/** Greedy word wrap to at most `maxChars` per line and `maxLines` lines; the last line ends with "..." if text was cut. */
export function wrapText(text: string, maxChars: number, maxLines: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (let word of normalise(text).split(/\s+/).filter(Boolean)) {
    while (word.length > maxChars) {
      if (line) {
        lines.push(line);
        line = "";
      }
      lines.push(word.slice(0, maxChars));
      word = word.slice(maxChars);
    }
    if (!line) line = word;
    else if (line.length + 1 + word.length <= maxChars) line += ` ${word}`;
    else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  kept[maxLines - 1] = `${kept[maxLines - 1]!.slice(0, Math.max(0, maxChars - 3))}...`;
  return kept;
}

class Canvas {
  readonly data = Buffer.alloc(CARD_WIDTH * CARD_HEIGHT * 3);

  fill([r, g, b]: Rgb): void {
    for (let i = 0; i < this.data.length; i += 3) {
      this.data[i] = r;
      this.data[i + 1] = g;
      this.data[i + 2] = b;
    }
  }

  rect(x: number, y: number, w: number, h: number, [r, g, b]: Rgb): void {
    for (let yy = Math.max(0, y); yy < Math.min(CARD_HEIGHT, y + h); yy++) {
      for (let xx = Math.max(0, x); xx < Math.min(CARD_WIDTH, x + w); xx++) {
        const i = (yy * CARD_WIDTH + xx) * 3;
        this.data[i] = r;
        this.data[i + 1] = g;
        this.data[i + 2] = b;
      }
    }
  }

  text(line: string, x: number, y: number, scale: number, color: Rgb): void {
    let cx = x;
    for (const ch of line) {
      const glyph = GLYPHS[ch];
      if (glyph) {
        glyph.forEach((row, r) => {
          for (let c = 0; c < GLYPH_COLS; c++) if (row[c] === "#") this.rect(cx + c * scale, y + r * scale, scale, scale, color);
        });
      }
      cx += ADVANCE_COLS * scale;
    }
  }
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf: Buffer): number {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, body: Buffer): Buffer {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(body.length, 0);
  head.write(type, 4, "ascii");
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), body])), 0);
  return Buffer.concat([head, body, crc]);
}

function encodePng(rgb: Buffer): Buffer {
  const stride = CARD_WIDTH * 3;
  const raw = Buffer.alloc((stride + 1) * CARD_HEIGHT);
  for (let y = 0; y < CARD_HEIGHT; y++) rgb.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  const header = Buffer.alloc(13);
  header.writeUInt32BE(CARD_WIDTH, 0);
  header.writeUInt32BE(CARD_HEIGHT, 4);
  header[8] = 8; // bit depth
  header[9] = 2; // truecolour RGB
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", header), chunk("IDAT", deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
}

export interface CardContent {
  /** Small eyebrow, e.g. "Chapter 9". */
  label: string;
  /** Main heading. */
  heading: string;
  /** Footer line, e.g. the site host. */
  footer: string;
}

/** Margin, type scales and line limits tuned so a 70-character heading fits on four lines. */
const MARGIN = 88;
const HEADING_SCALE = 7;
const HEADING_LINE_HEIGHT = 70;
const HEADING_MAX_LINES = 4;

export function renderCard({ label, heading, footer }: CardContent): Buffer {
  const canvas = new Canvas();
  canvas.fill(PAPER);
  canvas.rect(0, 0, 24, CARD_HEIGHT, ACCENT);

  canvas.text("RAG ARCHITECTURE HANDBOOK", MARGIN, 64, 4, MUTED);
  canvas.text(normalise(label), MARGIN, 150, 5, ACCENT);

  const maxChars = Math.floor((CARD_WIDTH - MARGIN * 2) / (ADVANCE_COLS * HEADING_SCALE));
  wrapText(heading, maxChars, HEADING_MAX_LINES).forEach((line, i) => canvas.text(line, MARGIN, 230 + i * HEADING_LINE_HEIGHT, HEADING_SCALE, INK));

  canvas.rect(MARGIN, CARD_HEIGHT - 110, CARD_WIDTH - MARGIN * 2, 3, INK);
  canvas.text(normalise(footer), MARGIN, CARD_HEIGHT - 74, 3, MUTED);
  return encodePng(canvas.data);
}
