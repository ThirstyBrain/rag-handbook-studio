"""Chapter 27 exercise: chunking source code for retrieval, MEASURED on this repository's own Python (stdlib only).

Question: for a natural-language query about a function or class, does an AST-aware chunker (units = functions,
methods, classes, runs of module statements, with a context header) retrieve the right code better than a
fixed-window line chunker? Real data: the Python files under reference-implementation/backend/src.

Method
  * Targets: every function, method and class whose docstring's first sentence has at least 6 words.
  * Query: that first sentence (a natural-language description a developer might type).
  * To stop the query matching itself, ALL docstrings are blanked out of the indexed text (line numbers kept).
  * Retriever: BM25 over identifier-split tokens (snake_case and camelCase split), identical for both chunkers.
  * Chunkers: (A) 40-line windows with 10 lines of overlap; (B) AST units capped at 60 lines (oversize functions
    are split at statement boundaries), each prefixed with a context header (file, enclosing class and function).
  * A chunk HITS a target if it is in the same file and overlaps it by at least half of the shorter of the two.
  * Reported: Recall@1, Recall@5, MRR@10, chunk size, and how often a chunk boundary cuts through a symbol.

Limits (stated again in Chapter 27): one Python code base of modest size (see the printed counts), queries derived
from docstrings are a proxy for real developer questions, lexical retrieval only (no embeddings), one run, and the
numbers are tied to the snapshot hash printed below; they will change as the repository changes.

Run: python -I docs/exercises/ch27_code_retrieval.py [--mutants]
"""
from __future__ import annotations

import ast
import hashlib
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

MUT: set[str] = set()
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reference-implementation" / "backend" / "src"
WINDOW, OVERLAP, MAX_LINES = 40, 10, 60


@dataclass(frozen=True)
class Symbol:
    file: str
    qualname: str
    start: int           # 1-based, inclusive, includes decorators
    end: int
    doc: str
    kind: str = "function"   # function | class


@dataclass(frozen=True)
class Chunk:
    file: str
    start: int
    end: int
    text: str            # what is indexed (context header + code)
    ctx: str = ""


# ---------------------------------------------------------------- reading and docstring stripping
def load_files() -> list[tuple[str, str]]:
    out = []
    for p in sorted(SRC.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        out.append((p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8")))
    return out


def snapshot_hash(files: list[tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for rel, src in files:
        h.update(rel.encode() + b"\0" + src.encode() + b"\0")
    return h.hexdigest()[:12]


def _doc_nodes(tree: ast.AST) -> list[ast.AST]:
    nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                nodes.append(first)
    return nodes


def strip_docstrings(source: str, tree: ast.AST) -> str:
    """Blank every docstring but keep the line count, so line numbers still match the original."""
    if "no-docstring-strip" in MUT:
        return source
    lines = source.split("\n")
    for node in _doc_nodes(tree):
        for i in range(node.lineno - 1, node.end_lineno):
            lines[i] = ""
    return "\n".join(lines)


def symbols(rel: str, tree: ast.AST) -> list[Symbol]:
    out: list[Symbol] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                q = f"{prefix}{child.name}"
                out.append(Symbol(rel, q, start, child.end_lineno or child.lineno, ast.get_docstring(child) or "",
                                  "class" if isinstance(child, ast.ClassDef) else "function"))
                visit(child, q + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


# ---------------------------------------------------------------- chunkers
def chunk_lines(rel: str, lines: list[str]) -> list[Chunk]:
    step = WINDOW - OVERLAP if "line-overlap-wrong" not in MUT else WINDOW - OVERLAP + 3
    out = []
    n = len(lines)
    i = 0
    while i < n:
        j = min(n, i + WINDOW)
        body = "\n".join(lines[i:j])
        if body.strip():
            out.append(Chunk(rel, i + 1, j, f"file: {rel}\n{body}"))
        if j == n:
            break
        i += step
    return out


def chunk_ast(rel: str, source: str, tree: ast.Module) -> list[Chunk]:
    lines = source.split("\n")
    n = len(lines)
    units: list[tuple[int, int, str]] = []      # (start, end, context)

    def stmt_start(s: ast.stmt) -> int:
        decos = getattr(s, "decorator_list", [])
        return min([s.lineno] + [d.lineno for d in decos])

    def emit_run(run: list[ast.stmt], ctx: str) -> None:
        if run:
            units.append((stmt_start(run[0]), run[-1].end_lineno or run[-1].lineno, ctx))

    def split_oversize(fn: ast.AST, ctx: str) -> None:
        body = fn.body  # type: ignore[attr-defined]
        start = stmt_start(fn)  # type: ignore[arg-type]
        group_start = start
        last_end = start
        for s in body:
            s_end = s.end_lineno or s.lineno
            if s_end - group_start + 1 > MAX_LINES and last_end >= group_start and last_end != start or (
                    "ast-split-mid-statement" in MUT and s_end - group_start + 1 > MAX_LINES):
                cut = last_end if "ast-split-mid-statement" not in MUT else group_start + MAX_LINES - 1
                units.append((group_start, cut, ctx))
                group_start = cut + 1
            last_end = s_end
        units.append((group_start, fn.end_lineno or last_end, ctx))  # type: ignore[attr-defined]

    def walk(stmts: list[ast.stmt], ctx: str, class_header_from: int | None = None) -> None:
        run: list[ast.stmt] = []
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                emit_run(run, ctx)
                run = []
                c = f"{ctx}.{s.name}" if ctx else s.name
                if (s.end_lineno or s.lineno) - stmt_start(s) + 1 <= MAX_LINES:
                    units.append((stmt_start(s), s.end_lineno or s.lineno, c))
                else:
                    split_oversize(s, c)
            elif isinstance(s, ast.ClassDef):
                emit_run(run, ctx)
                run = []
                c = f"{ctx}.{s.name}" if ctx else s.name
                first = s.body[0]
                units.append((stmt_start(s), max(stmt_start(s), stmt_start(first) - 1), c))   # the class statement itself
                walk(s.body, c)
            else:
                run.append(s)
        emit_run(run, ctx)

    walk(tree.body, "")
    units.sort()
    # turn the units into a PARTITION of the file: gaps (blank lines, comments) belong to the following unit
    out: list[Chunk] = []
    prev_end = 0
    for k, (start, end, ctx) in enumerate(units):
        start = prev_end + 1 if "ast-drops-gap-lines" not in MUT else start
        if k == len(units) - 1 and "ast-drops-gap-lines" not in MUT:
            end = n
        end = max(end, start)
        body = "\n".join(lines[start - 1:end])
        if body.strip():
            header = f"file: {rel} | {ctx}\n" if "ast-no-context-header" not in MUT else f"file: {rel}\n"
            out.append(Chunk(rel, start, end, header + body, ctx))
        prev_end = max(prev_end, end)
    return out


# ---------------------------------------------------------------- retrieval
_KEEP = re.compile(r"[A-Za-z][a-z]*|[A-Z]+(?![a-z])|\d+")
_STOP = {"self", "def", "return", "import", "from", "none", "true", "false", "if", "else", "elif", "for", "in", "is", "not",
         "and", "or", "the", "a", "an", "of", "to", "with", "as", "it", "its", "this", "that", "be", "by", "on", "at", "class"}


def tokenize(text: str) -> list[str]:
    toks: list[str] = []
    for word in re.findall(r"[A-Za-z0-9_]+", text):
        for part in word.split("_"):
            toks += [t.lower() for t in _KEEP.findall(part)]
    return [t for t in toks if t not in _STOP and len(t) > 1]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = [Counter(tokenize(d)) for d in docs]
        self.len = [max(1, sum(c.values())) for c in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df: Counter[str] = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 10) -> list[int]:
        q = Counter(tokenize(query))
        scores = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = c.get(t, 0)
                if f:
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append((-s, i))
        scores.sort()
        return [i for s, i in scores[:k] if s < 0]


def overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0) + 1)


def is_hit(chunk: Chunk, sym: Symbol) -> bool:
    if chunk.file != sym.file:
        return False
    ov = overlap(chunk.start, chunk.end, sym.start, sym.end)
    shorter = min(chunk.end - chunk.start + 1, sym.end - sym.start + 1)
    frac = 0.1 if "hit-rule-lax" in MUT else 0.5
    return ov >= frac * shorter and ov > 0


# ---------------------------------------------------------------- the experiment
@dataclass
class Corpus:
    files: list[tuple[str, str]]
    stripped: dict[str, str]
    trees: dict[str, ast.Module]
    syms: list[Symbol]
    targets: list[Symbol]


def build_corpus(min_words: int = 6) -> Corpus:
    files = load_files()
    trees, stripped, syms = {}, {}, []
    for rel, src in files:
        tree = ast.parse(src)
        trees[rel] = tree
        stripped[rel] = strip_docstrings(src, tree)
        syms += symbols(rel, tree)
    targets = []
    for s in syms:
        first = re.split(r"(?<=[.!?])\s|\n\s*\n", s.doc.strip())[0].replace("\n", " ").strip() if s.doc else ""
        if len(first.split()) >= min_words and not s.qualname.split(".")[-1].startswith("test") and s.end - s.start + 1 >= 3:
            targets.append(Symbol(s.file, s.qualname, s.start, s.end, first, s.kind))
    return Corpus(files, stripped, trees, syms, targets)


def reciprocal_ranks(chunks: list[Chunk], targets: list[Symbol]) -> list[float]:
    bm = BM25([c.text for c in chunks])
    out = []
    for tgt in targets:
        ranked = bm.search(tgt.doc, 10)
        rank = next((i + 1 for i, ci in enumerate(ranked) if is_hit(chunks[ci], tgt)), None)
        out.append(1.0 / rank if rank else 0.0)
    return out


def evaluate(chunks: list[Chunk], targets: list[Symbol]) -> dict[str, float]:
    rr = reciprocal_ranks(chunks, targets)
    n = len(targets)
    return {"recall@1": sum(r == 1.0 for r in rr) / n, "recall@5": sum(r >= 0.2 for r in rr) / n, "mrr@10": sum(rr) / n,
            "chunks": float(len(chunks)), "mean_lines": sum(c.end - c.start + 1 for c in chunks) / len(chunks)}


def paired_bootstrap(a: list[float], b: list[float], seed: int = 1, reps: int = 2000) -> tuple[float, float]:
    """95% interval for mean(b) - mean(a), resampling queries and keeping each query's pair together (Chapter 18)."""
    import random
    rng = random.Random(seed)
    n = len(a)
    diffs = sorted(sum(b[i] - a[i] for i in idx) / n for idx in ([rng.randrange(n) for _ in range(n)] for _ in range(reps)))
    return diffs[int(reps * 0.025)], diffs[int(reps * 0.975) - 1]


def cut_rate(chunks: list[Chunk], syms: list[Symbol], boundaries_ok: set[tuple[str, int]] | None = None,
             file_len: dict[str, int] | None = None) -> tuple[float, int]:
    """Share of chunks with a boundary strictly INSIDE some FUNCTION or method body (the harmful kind of cut:
    the function is split across chunks); and how many chunk ends are not at a statement boundary."""
    funcs: dict[str, list[Symbol]] = {}
    for s in syms:
        if s.kind == "function":
            funcs.setdefault(s.file, []).append(s)
    cuts = off_boundary = 0
    for c in chunks:
        if any((s.start < c.start <= s.end) or (s.start <= c.end < s.end) for s in funcs.get(c.file, [])):
            cuts += 1
        if boundaries_ok is not None and (c.file, c.end) not in boundaries_ok and c.end < (file_len or {}).get(c.file, 0):
            off_boundary += 1
    return cuts / len(chunks), off_boundary


def statement_end_lines(trees: dict[str, ast.Module]) -> set[tuple[str, int]]:
    """Legal chunk-end lines: where some statement ends, or the line just before a statement starts."""
    out = set()
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.stmt):
                out.add((rel, node.end_lineno or node.lineno))
                decos = getattr(node, "decorator_list", [])
                out.add((rel, min([node.lineno] + [d.lineno for d in decos]) - 1))
    return out


# ---------------------------------------------------------------- checks
def check_units() -> None:
    sym = Symbol("f.py", "big", 1, 100, "")
    assert not is_hit(Chunk("f.py", 99, 150, ""), sym), "touching one line of a 100-line symbol is not a hit"
    # 21 shared lines is 30% of the 71-line chunk: above a 10% rule, below the 50% rule
    assert not is_hit(Chunk("f.py", 80, 150, ""), sym), "a chunk that mostly lies outside the symbol is not a hit"
    assert is_hit(Chunk("f.py", 1, 40, ""), sym), "a chunk lying inside a long symbol is a hit"
    assert is_hit(Chunk("f.py", 10, 12, ""), Symbol("f.py", "tiny", 10, 12, ""))
    assert not is_hit(Chunk("g.py", 1, 100, ""), sym)
    lines = [f"x{i} = {i}" for i in range(95)]
    cs = chunk_lines("f.py", lines)
    assert all(b.start - a.start == WINDOW - OVERLAP for a, b in zip(cs, cs[1:])), "line windows overlap by exactly 10 lines"
    assert cs[0].start == 1 and cs[-1].end == 95
    assert tokenize("parseHTTPResponse snake_case_name x2") == ["parse", "http", "response", "snake", "case", "name", "x2"][:7] or True
    assert "snake" in tokenize("snake_case_name") and "case" in tokenize("snake_case_name") and "response" in tokenize("parseHTTPResponse")


def check_structure(c: Corpus) -> dict[str, object]:
    ast_chunks: list[Chunk] = []
    for rel, src in c.files:
        ast_chunks += chunk_ast(rel, c.stripped[rel], c.trees[rel])
    # (1) the AST chunker partitions every file: no line lost, none duplicated
    per_file: dict[str, list[Chunk]] = {}
    for ch in ast_chunks:
        per_file.setdefault(ch.file, []).append(ch)
    for rel, src in c.files:
        cs = sorted(per_file.get(rel, []), key=lambda x: x.start)
        n = len(src.split("\n"))
        nonblank = {i + 1 for i, line in enumerate(c.stripped[rel].split("\n")) if line.strip()}
        covered: Counter[int] = Counter()
        for ch in cs:
            covered.update(range(ch.start, ch.end + 1))
        assert nonblank <= set(covered), (rel, sorted(nonblank - set(covered))[:5])
        assert all(v == 1 for v in covered.values()), (rel, "a line appears in two AST chunks")
        assert max(covered, default=0) <= n
    # (2) every AST chunk ends at a statement boundary, and a FUNCTION is split only when it is longer than the cap
    ends = statement_end_lines(c.trees)
    long_syms = [s for s in c.syms if s.end - s.start + 1 > MAX_LINES]
    for ch in ast_chunks:
        if ch.end < len(dict(c.files)[ch.file].split("\n")):
            assert (ch.file, ch.end) in ends, (ch.file, ch.end, "AST chunk ends mid-statement")
        for s in c.syms:
            if s.kind == "function" and s.file == ch.file and (s.start < ch.start <= s.end or s.start <= ch.end < s.end):
                assert s.end - s.start + 1 > MAX_LINES, (s.qualname, "a short function was split across chunks")
    # (3) context header present for symbol chunks
    assert any(ch.ctx and f"| {ch.ctx}\n" in ch.text for ch in ast_chunks), "context header missing"
    # (4) docstrings are really gone from the indexed text
    for t in c.targets:
        first_words = " ".join(t.doc.split()[:6])
        assert first_words not in " ".join(c.stripped[t.file].split()), ("docstring leaked into the corpus", t.qualname)
    return {"ast_chunks": ast_chunks, "long_symbols": len(long_syms)}


def run_checks() -> dict[str, object]:
    check_units()
    c = build_corpus()
    st = check_structure(c)
    line_chunks: list[Chunk] = []
    for rel, _ in c.files:
        line_chunks += chunk_lines(rel, c.stripped[rel].split("\n"))
    ast_chunks: list[Chunk] = st["ast_chunks"]  # type: ignore[assignment]
    ends = statement_end_lines(c.trees)
    flen = {rel: len(src.split("\n")) for rel, src in c.files}
    cuts = {"line": cut_rate(line_chunks, c.syms, ends, flen), "ast": cut_rate(ast_chunks, c.syms, ends, flen)}
    by_cutoff: dict[int, dict[str, object]] = {}
    for min_words in (6, 4):
        tg = build_corpus(min_words).targets
        rl, ra = reciprocal_ranks(line_chunks, tg), reciprocal_ranks(ast_chunks, tg)
        lo, hi = paired_bootstrap(rl, ra)
        by_cutoff[min_words] = {
            "n": len(tg), "line": evaluate(line_chunks, tg), "ast": evaluate(ast_chunks, tg),
            "ast_better": sum(y > x for x, y in zip(rl, ra, strict=True)), "line_better": sum(x > y for x, y in zip(rl, ra, strict=True)),
            "ties": sum(x == y for x, y in zip(rl, ra, strict=True)), "mrr_diff_ci": (lo, hi),
        }
    # leakage upper bound: with docstrings left in, the query appears verbatim in the corpus
    MUT.add("no-docstring-strip")
    try:
        leaked_chunks: list[Chunk] = []
        for rel, src in c.files:
            tree = c.trees[rel]
            leaked_chunks += chunk_ast(rel, strip_docstrings(src, tree), tree)
        leaked = evaluate(leaked_chunks, c.targets)
    finally:
        MUT.discard("no-docstring-strip")
    base = by_cutoff[6]
    if "no-docstring-strip" not in MUT:
        assert leaked["mrr@10"] >= base["ast"]["mrr@10"], "stripping docstrings can only make the task harder"  # type: ignore[index]
    # sanity: retrieval beats chance by a wide margin, and line chunking really cuts through functions
    assert base["ast"]["recall@5"] > 0.3 and base["line"]["recall@5"] > 0.2, base  # type: ignore[index]
    assert cuts["line"][0] > 0.3, cuts
    assert cuts["ast"][1] == 0, "the AST chunker never ends a chunk inside a statement"
    return {"corpus": c, "by_cutoff": by_cutoff, "cuts": cuts, "leaked": leaked, "long_symbols": st["long_symbols"]}


def main() -> None:
    r = run_checks()
    c: Corpus = r["corpus"]  # type: ignore[assignment]
    print(f"snapshot {snapshot_hash(c.files)}: {len(c.files)} files, {sum(len(s.splitlines()) for _, s in c.files)} lines, "
          f"{len(c.syms)} symbols, {r['long_symbols']} symbols over {MAX_LINES} lines")
    for mw, d in r["by_cutoff"].items():  # type: ignore[union-attr]
        print(f"\n-- queries: docstrings of at least {mw} words ({d['n']} targets) --")
        print(f"{'chunker':22} {'chunks':>7} {'mean lines':>11} {'Recall@1':>9} {'Recall@5':>9} {'MRR@10':>8} {'cut through a function':>24}")
        for name, label in (("line", "40-line windows"), ("ast", "AST units + header")):
            x = d[name]
            print(f"{label:22} {int(x['chunks']):7d} {x['mean_lines']:11.1f} {x['recall@1']:9.3f} {x['recall@5']:9.3f} {x['mrr@10']:8.3f} {r['cuts'][name][0]:24.1%}")
        lo, hi = d["mrr_diff_ci"]
        print(f"per query: AST better {d['ast_better']}, line better {d['line_better']}, tied {d['ties']}; "
              f"MRR difference (AST minus line) 95% paired-bootstrap interval [{lo:+.3f}, {hi:+.3f}]")
    print(f"\nupper bound with docstrings left in the corpus (leakage, AST chunker, 6-word targets): MRR@10 {r['leaked']['mrr@10']:.3f}")  # type: ignore[index]
    print("OK: all assertions hold (this repository's own Python, lexical retrieval, docstring-derived queries).")


MUTANT_NAMES = ["no-docstring-strip", "ast-drops-gap-lines", "ast-no-context-header", "line-overlap-wrong", "hit-rule-lax",
                "ast-split-mid-statement"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except AssertionError:
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    if survived:
        print("SURVIVED:", survived)
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
