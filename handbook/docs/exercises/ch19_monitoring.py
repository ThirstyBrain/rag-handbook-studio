"""Chapter 19 exercise: monitoring that pages for the right reasons (stdlib only).

  A. error-budget arithmetic: reproduces the budget-consumed column of the SRE Workbook table (S138);
  B. multiwindow, multi-burn-rate alerting evaluated on simulated per-minute traffic, against a naive
     threshold alert: time to detect, precision on short spikes, reset time, and a case that is (by design)
     NOT alerted because it consumes less budget than any rule's threshold;
  C. a sampled quality SLI ("answer was grounded", judged on a sample of requests): Wilson interval,
     detection delay versus sampling rate, false alerts in the stable state (SIMULATION, synthetic);
  D. telemetry hygiene: content capture off by default (S137), attribute allow-list, errors recorded by
     class name only, and a metric-label cardinality guard;
  E. a mutation check of the monitoring logic itself.

Run: python -I docs/exercises/ch19_monitoring.py [--mutants]
Traffic, error ratios and quality rates are CONSTRUCTED for teaching. Nothing here measures a real system.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass

MUT: set[str] = set()

SLO = 0.999
BUDGET = 1 - SLO  # allowed error ratio
PERIOD_MIN = 30 * 24 * 60  # the SLO window: 30 days of minutes


# ---------------------------------------------------------------- A. budget arithmetic
def burn_rate(error_ratio: float) -> float:
    """How many times faster than 'exactly on budget' the budget is being spent."""
    return error_ratio / BUDGET


def budget_consumed(burn: float, window_min: int) -> float:
    """Share of the whole 30-day budget spent by burning at `burn` for `window_min` minutes."""
    return burn * window_min / (PERIOD_MIN + (1 if "period-off-by-one" in MUT else 0))


# ---------------------------------------------------------------- B. burn-rate alert rules
@dataclass(frozen=True)
class Rule:
    name: str
    long_min: int
    short_min: int
    burn: float
    severity: str


# Table 5-8 of the SRE Workbook for a 99.9% SLO (S138): page at 2% and 5% budget, ticket at 10%.
RULES = (
    Rule("fast", 60, 5, 14.4, "page"),
    Rule("medium", 360, 30, 6.0, "page"),
    Rule("slow", 4320, 360, 1.0, "ticket"),
)


def _ratio(total: list[int], bad: list[int], t: int, window: int) -> float:
    lo = max(0, t - window + 1)
    tot = sum(total[lo : t + 1])
    return sum(bad[lo : t + 1]) / tot if tot else 0.0


def firing(total: list[int], bad: list[int], rule: Rule, t: int) -> bool:
    long_burn = burn_rate(_ratio(total, bad, t, rule.long_min))
    short_burn = burn_rate(_ratio(total, bad, t, rule.short_min))
    if "single-window" in MUT:
        return long_burn >= rule.burn
    if "short-window-only" in MUT:
        return short_burn >= rule.burn
    return long_burn >= rule.burn and short_burn >= rule.burn


def naive_alert(total: list[int], bad: list[int], t: int) -> bool:
    """'Error ratio over the last 5 minutes exceeds the SLO error rate': fast, but ignores how much budget is at stake."""
    return burn_rate(_ratio(total, bad, t, 5)) > 1.0


def first_and_last(flags: list[bool]) -> tuple[int | None, int | None]:
    idx = [i for i, f in enumerate(flags) if f]
    return (idx[0], idx[-1]) if idx else (None, None)


HISTORY = 4400  # healthy minutes before an incident, so every window is full (3 days = 4320)


def traffic(history_bad: float, segments: list[tuple[int, float]], rpm: int = 1000) -> tuple[list[int], list[int]]:
    """Per-minute (total, bad). segments: (minutes, error_ratio) after a healthy history."""
    ratios = [history_bad] * HISTORY
    for minutes, ratio in segments:
        ratios += [ratio] * minutes
    total = [rpm] * len(ratios)
    bad = [round(rpm * r) for r in ratios]
    return total, bad


def run_rules(total: list[int], bad: list[int]) -> dict[str, list[bool]]:
    return {r.name: [firing(total, bad, r, t) for t in range(len(total))] for r in RULES}


# ---------------------------------------------------------------- C. sampled quality SLI
Z = 1.96


def wilson(bad: int, n: int) -> tuple[float, float]:
    z = 1.0 if "wilson-z-wrong" in MUT else Z
    p = bad / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def quality_alert(bad: int, n: int, threshold: float, min_samples: int = 50) -> bool:
    """Alert when we are confident the ungrounded rate exceeds the threshold (lower bound above it)."""
    if n < min_samples and "no-min-samples" not in MUT:
        return False
    if "point-estimate-alert" in MUT:
        return bad / n > threshold
    return wilson(bad, n)[0] > threshold


def requests_until_alert(true_rate: float, sample_rate: float, threshold: float, rng: random.Random,
                         max_requests: int = 60_000, window: int = 400) -> int | None:
    """Judge a random sample of requests; keep the last `window` verdicts; return the request count at first alert."""
    verdicts: list[bool] = []
    for i in range(1, max_requests + 1):
        if rng.random() < sample_rate:
            verdicts.append(rng.random() < true_rate)
            verdicts = verdicts[-window:]
            if quality_alert(sum(verdicts), len(verdicts), threshold):
                return i
    return None


# ---------------------------------------------------------------- D. telemetry hygiene
ALLOWED_SPAN_ATTRS = frozenset({
    "gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model",
    "gen_ai.response.finish_reasons", "error.type", "rag.route", "rag.embedding_space", "rag.k",
    "rag.chunks_returned", "rag.tenant_tier",
})
CONTENT_ATTRS = frozenset({"gen_ai.output.messages", "rag.query_text", "rag.chunk_text"})
CAPTURE_VALUES = {"NO_CONTENT", "SPAN_ONLY", "EVENT_ONLY", "SPAN_AND_EVENT"}
METRIC_LABELS = frozenset({"gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "rag.route",
                           "error.type", "rag.tenant_tier"})
MAX_LABEL_VALUES = 20  # a metric label with more distinct values than this is a cardinality bug


def build_span_attrs(attrs: dict[str, object], capture: str = "NO_CONTENT") -> dict[str, object]:
    """Allow-list, never block-list: an attribute nobody reviewed is not exported. Content only on explicit opt-in;
    an invalid capture setting falls back to NO_CONTENT (S137)."""
    mode = capture if capture in CAPTURE_VALUES else "NO_CONTENT"
    if "capture-default-on" in MUT and capture not in CAPTURE_VALUES:
        mode = "SPAN_ONLY"
    out = {}
    for k, v in attrs.items():
        if k in CONTENT_ATTRS:
            if mode in {"SPAN_ONLY", "SPAN_AND_EVENT"}:
                out[k] = v
        elif k in ALLOWED_SPAN_ATTRS or "allow-list-bypass" in MUT:
            out[k] = v
    return out


def error_attrs(exc: BaseException) -> dict[str, object]:
    """Record the exception CLASS only: messages can carry URLs, keys and prompt fragments."""
    attrs: dict[str, object] = {"error.type": type(exc).__name__}
    if "error-message-leak" in MUT:
        attrs["exception.message"] = str(exc)
    return attrs


class LabelGuard:
    """Refuses metric labels that are not allow-listed and bounds the distinct values per label."""

    def __init__(self) -> None:
        self.seen: dict[str, set[str]] = {}

    def labels(self, attrs: dict[str, object]) -> dict[str, str]:
        out = {}
        for k, v in attrs.items():
            if k not in METRIC_LABELS:
                if "label-allow-list-bypass" in MUT:
                    out[k] = str(v)
                continue
            vals = self.seen.setdefault(k, set())
            vals.add(str(v))
            if len(vals) > MAX_LABEL_VALUES and "no-cardinality-cap" not in MUT:
                out[k] = "other"
            else:
                out[k] = str(v)
        return out


# ---------------------------------------------------------------- checks
def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def check_budget_math() -> None:
    # the budget-consumed column of the published table (S138): 2%, 5%, 10%
    assert approx(budget_consumed(14.4, 60), 0.02)
    assert approx(budget_consumed(6.0, 360), 0.05)
    assert approx(budget_consumed(1.0, 4320), 0.10)
    assert approx(burn_rate(0.001), 1.0) and approx(burn_rate(0.0144), 14.4)
    # a 35x burn exhausts a 30-day budget in about 20.5 hours (the single-burn-rate failure case in S138)
    assert approx(PERIOD_MIN / 35 / 60, 20.571428571428573)


def check_alerting() -> dict[str, object]:
    # 1. total outage for 60 minutes
    total, bad = traffic(0.0, [(60, 1.0), (400, 0.0)])
    start = HISTORY
    fl = run_rules(total, bad)
    page = [a or b for a, b in zip(fl["fast"], fl["medium"], strict=True)]
    first, last = first_and_last(page)
    assert first == start, "a total outage pages in the first bad minute"
    reset_min = last - (start + 59)  # minutes after the outage ended until the page clears
    assert 25 <= reset_min <= 35, reset_min  # the 30-minute short window of the medium rule sets the reset time
    assert first_and_last(fl["fast"])[1] - (start + 59) <= 5, "the fast rule clears 5 minutes after the outage"

    # 2. slow burn at 2x for 4 days: no page, a ticket once 10% of the budget is gone
    total, bad = traffic(0.0, [(5760, 0.002)])
    fl = run_rules(total, bad)
    assert first_and_last(fl["fast"])[0] is None and first_and_last(fl["medium"])[0] is None
    t_ticket = first_and_last(fl["slow"])[0]
    assert t_ticket is not None
    elapsed = t_ticket - HISTORY
    assert 2100 <= elapsed <= 2200, elapsed  # ~36 h
    assert approx(budget_consumed(2.0, elapsed), 0.1, 0.01), "the ticket fires when about 10% of the budget is spent"

    # 3. a 10-minute spike at 0.5% errors: the naive alert fires, the multiwindow rules stay silent
    total, bad = traffic(0.0, [(10, 0.005), (200, 0.0)])
    naive = [naive_alert(total, bad, t) for t in range(len(total))]
    fl = run_rules(total, bad)
    assert any(naive), "naive threshold alert pages on a blip"
    assert not any(any(v) for v in fl.values()), "multiwindow alerts ignore a blip that costs ~0.1% of the budget"
    blip_cost = budget_consumed(5.0, 10)
    assert blip_cost < 0.002

    # 4. 10x burn for 3 hours consumes ~4% of the budget: below every rule's threshold, so NO alert (by design)
    total, bad = traffic(0.0, [(180, 0.01), (300, 0.0)])
    fl = run_rules(total, bad)
    consumed = budget_consumed(10.0, 180)
    assert not any(any(v) for v in fl.values()), "incidents cheaper than the thresholds are not alerted"
    assert 0.04 < consumed < 0.05, consumed
    return {"reset_min": reset_min, "ticket_after_min": elapsed, "blip_cost": blip_cost, "quiet_incident_cost": consumed}


def check_wilson_and_quality() -> dict[str, object]:
    lo, hi = wilson(0, 10)
    assert approx(lo, 0.0, 1e-9) and approx(hi, 0.2775, 5e-4), (lo, hi)  # known value: 0 of 10
    lo, hi = wilson(50, 100)
    assert approx(lo, 0.4038, 5e-4) and approx(hi, 0.5962, 5e-4), (lo, hi)
    assert quality_alert(4, 10, 0.05) is False, "too few samples: no alert"
    assert quality_alert(30, 200, 0.05) is True  # 15% of 200: clearly above 5%
    assert quality_alert(13, 200, 0.05) is False, "6.5% observed, but the lower bound is below 5%: not yet confident"
    # detection delay versus sampling rate (true ungrounded rate rises to 12%; alert threshold 5%)
    delays = {}
    for rate in (0.01, 0.05, 0.20):
        runs = [requests_until_alert(0.12, rate, 0.05, random.Random(1000 * i + int(rate * 100))) for i in range(15)]
        assert all(r is not None for r in runs), (rate, runs)
        delays[rate] = sorted(runs)[len(runs) // 2]
    assert delays[0.20] < delays[0.05] < delays[0.01], delays
    # stable state at 3% ungrounded: how many of 20 simulated 20,000-request days raise a false alert at 5% sampling?
    false = sum(requests_until_alert(0.03, 0.05, 0.05, random.Random(500 + i), max_requests=20_000) is not None
                for i in range(20))
    assert false <= 2, false
    return {"median_requests_to_alert": delays, "false_alert_days_of_20": false}


def check_telemetry_hygiene() -> None:
    attrs = {
        "gen_ai.operation.name": "embeddings", "gen_ai.request.model": "m", "rag.route": "embed",
        "rag.query_text": "what is the salary of Jane Doe?", "rag.chunk_text": "confidential...",
        "gen_ai.output.messages": "...", "user.id": "u-123", "http.request.header.authorization": "Bearer x",
    }
    safe = build_span_attrs(attrs)
    assert set(safe) == {"gen_ai.operation.name", "gen_ai.request.model", "rag.route"}, safe
    assert "rag.query_text" in build_span_attrs(attrs, "SPAN_ONLY"), "content only on explicit opt-in"
    assert "rag.query_text" not in build_span_attrs(attrs, "EVENT_ONLY"), "event-only capture is not span capture"
    assert "rag.query_text" not in build_span_attrs(attrs, "yes please"), "an invalid setting falls back to NO_CONTENT"
    assert "user.id" not in build_span_attrs(attrs, "SPAN_AND_EVENT"), "unreviewed attributes are never exported"
    err = error_attrs(RuntimeError("connect to https://x?key=SECRET failed"))
    assert err == {"error.type": "RuntimeError"}, err
    guard = LabelGuard()
    first = guard.labels({"rag.route": "answer", "tenant_id": "t-1", "request_id": "r-1"})
    assert first == {"rag.route": "answer"}, "identifiers are never metric labels"
    for i in range(MAX_LABEL_VALUES + 15):
        last = guard.labels({"rag.tenant_tier": f"tier-{i}"})
    assert last == {"rag.tenant_tier": "other"}, "a label that explodes in cardinality collapses to 'other'"


def run_checks() -> dict[str, object]:
    check_budget_math()
    out: dict[str, object] = dict(check_alerting())
    out.update(check_wilson_and_quality())
    check_telemetry_hygiene()
    return out


def main() -> None:
    r = run_checks()
    print("outage page clears", r["reset_min"], "min after the outage ends (30-minute short window of the medium rule)")
    print("2x slow burn: ticket after", r["ticket_after_min"], "min (~36 h); 10-minute 0.5% blip costs",
          f"{r['blip_cost']:.4%}", "of the budget and pages nobody")
    print("10x burn for 3 h costs", f"{r['quiet_incident_cost']:.1%}", "of the budget: below every threshold, not alerted")
    print("median requests until the quality alert (12% true rate vs 5% threshold), by sample rate:",
          r["median_requests_to_alert"], "| false-alert days at 3% true rate (5% sampling):", r["false_alert_days_of_20"], "of 20")
    print("OK: all assertions hold (constructed traffic and synthetic simulation; no real service measured).")


MUTANT_NAMES = ["period-off-by-one", "single-window", "short-window-only", "wilson-z-wrong", "no-min-samples",
                "point-estimate-alert", "capture-default-on", "allow-list-bypass", "error-message-leak",
                "label-allow-list-bypass", "no-cardinality-cap"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except (AssertionError, TypeError, ZeroDivisionError):
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
