"""Chapter 21 exercise: how retries, queues and breakers behave when a dependency degrades (stdlib only).

A time-stepped simulation (1 tick = one unit of time). Clients send LAMBDA new requests per tick to a
dependency with a FIFO queue and capacity CAP per tick. For ticks FAIL_START..FAIL_END the capacity drops to
FAIL_CAP (a provider brown-out). A client gives up after TIMEOUT ticks; the dependency still spends capacity on
a request whose client has already given up unless it sheds expired work. Clients retry according to a policy.
Measured per policy: load amplification (attempts per new request), peak queue, success ratio during the
brown-out, and ticks until the system is healthy again.

  A. retry policies compared: none, immediate, exponential without jitter, full jitter, jitter + retry budget,
     + deadline-aware shedding with a bounded queue, + circuit breaker;
  B. deadline propagation arithmetic; idempotency keys for retried side effects;
  C. a mutation check of the policies.

Run: python -I docs/exercises/ch21_resilience.py [--mutants]
The model is deliberately simple and its parameters (LAMBDA, CAP, TIMEOUT, ...) are MY CHOICES: it demonstrates a
mechanism (work amplification and wasted work), not the size of the effect in any real system.
"""
from __future__ import annotations

import random
import sys
from collections import deque
from dataclasses import dataclass, field

MUT: set[str] = set()

LAMBDA = 70          # new requests per tick (70% of normal capacity)
CAP = 100            # dependency capacity per tick
FAIL_START, FAIL_END = 100, 130
FAIL_CAP = 20        # capacity during the brown-out
TIMEOUT = 5          # ticks before a client gives up
HORIZON = 400


@dataclass(frozen=True)
class Policy:
    name: str
    max_retries: int = 0
    backoff: str = "none"            # none | exp | jitter
    base: int = 2
    budget: float | None = None      # retry tokens earned per new request (None = unlimited)
    breaker: bool = False
    shed_expired: bool = False       # server skips queued requests whose client has already given up
    queue_cap: int | None = None     # server queue bound; a full queue rejects immediately


@dataclass
class Origin:
    born: int
    done: bool = False
    failed: bool = False


@dataclass
class Req:
    origin: Origin
    attempt: int
    deadline: int
    served: bool = False


@dataclass
class Result:
    amplification: float
    peak_queue: int
    success_in_brownout: float
    recovery_tick: int | None
    rejected: int = 0
    wasted: int = 0
    attempts: int = 0
    origins: int = 0
    _by_tick: dict[int, list[Origin]] = field(default_factory=dict)


def retry_delay(p: Policy, attempt: int, rng: random.Random) -> int:
    """Ticks to wait before retry number `attempt + 1`."""
    if p.backoff == "none" or "no-backoff" in MUT:
        return 1
    ceiling = p.base * 2**attempt
    if p.backoff == "exp" or "no-jitter" in MUT:
        return ceiling
    return 1 + rng.randint(0, ceiling)  # full jitter: spread uniformly over the whole window


def herd_peak(p: Policy, clients: int = 1000, seed: int = 3) -> int:
    """All `clients` fail at the same instant (for example a dropped connection) and every retry fails too.
    Returns the largest number of retries that land on any single tick: the size of the thundering herd."""
    rng = random.Random(seed)
    load: dict[int, int] = {}
    for _ in range(clients):
        t = 0
        for attempt in range(p.max_retries):
            t += retry_delay(p, attempt, rng)
            load[t] = load.get(t, 0) + 1
    return max(load.values())


def simulate(p: Policy, seed: int = 1) -> Result:
    rng = random.Random(seed)
    queue: deque[Req] = deque()
    timeouts: dict[int, list[Req]] = {}
    retries: dict[int, list[tuple[Origin, int]]] = {}
    origins: list[Origin] = []
    tokens = 0.0
    attempts = rejected = wasted = peak = 0
    # breaker state
    b_open_until = -1
    b_failures = 0
    b_trials_left = 0
    B_THRESHOLD, B_OPEN_TICKS, B_TRIALS = 20, 10, 5

    def breaker_allows(t: int) -> bool:
        nonlocal b_trials_left
        if not p.breaker or "breaker-never-opens" in MUT:
            return True
        if t < b_open_until:
            return False
        if b_open_until >= 0 and b_trials_left > 0:  # half-open: a few trial requests
            b_trials_left -= 1
            return True
        return b_open_until < 0

    def breaker_record(ok: bool, t: int) -> None:
        nonlocal b_failures, b_open_until, b_trials_left
        if not p.breaker or "breaker-never-opens" in MUT:
            return
        if ok:
            b_failures, b_open_until = 0, -1
        else:
            b_failures += 1
            if b_failures >= B_THRESHOLD:
                b_open_until, b_trials_left, b_failures = t + B_OPEN_TICKS, B_TRIALS, 0

    def on_failure(o: Origin, attempt: int, t: int) -> None:
        nonlocal tokens
        if o.done or o.failed:
            return
        if attempt >= p.max_retries:
            o.failed = True
            return
        if p.budget is not None and "budget-ignored" not in MUT:
            if tokens < 1:
                o.failed = True
                return
            tokens -= 1
        retries.setdefault(t + retry_delay(p, attempt, rng), []).append((o, attempt + 1))

    def submit(o: Origin, attempt: int, t: int) -> None:
        nonlocal attempts, rejected
        if not breaker_allows(t):
            on_failure(o, attempt, t)  # fail fast: no load on the dependency, and the retry policy still applies
            return
        attempts += 1
        if p.queue_cap is not None and len(queue) >= p.queue_cap:
            rejected += 1
            breaker_record(False, t)
            on_failure(o, attempt, t)
            return
        req = Req(o, attempt, t + TIMEOUT)
        queue.append(req)
        timeouts.setdefault(t + TIMEOUT + 1, []).append(req)

    for t in range(HORIZON):
        for _ in range(LAMBDA):
            o = Origin(born=t)
            origins.append(o)
            tokens = min(tokens + (p.budget or 0.0), 50.0)
            submit(o, 0, t)
        for o, attempt in retries.pop(t, []):
            if not (o.done or o.failed):
                submit(o, attempt, t)
        cap = FAIL_CAP if FAIL_START <= t < FAIL_END else CAP
        while cap > 0 and queue:
            req = queue.popleft()
            if p.shed_expired and req.deadline < t and "shedding-disabled" not in MUT:
                continue  # the client has already given up: no capacity spent
            cap -= 1
            if t <= req.deadline:
                req.served = True
                req.origin.done = True
                breaker_record(True, t)
            else:
                wasted += 1  # work for a client that is no longer waiting
        for req in timeouts.pop(t, []):
            if not req.served:
                breaker_record(False, t)
                on_failure(req.origin, req.attempt, t)
        peak = max(peak, len(queue))

    by_tick: dict[int, list[Origin]] = {}
    for o in origins:
        by_tick.setdefault(o.born, []).append(o)
    ratio = {t: sum(o.done for o in os) / len(os) for t, os in by_tick.items()}
    brown = [o for o in origins if FAIL_START <= o.born < FAIL_END]
    success_brown = sum(o.done for o in brown) / len(brown)
    recovery = None
    for t in range(FAIL_END, HORIZON - 20):
        if all(ratio[u] >= 0.99 for u in range(t, HORIZON - 20)):
            recovery = t - FAIL_END
            break
    return Result(attempts / len(origins), peak, success_brown, recovery, rejected, wasted, attempts, len(origins))


# ---------------------------------------------------------------- B. deadlines and idempotency
def child_timeout(parent_remaining: float, stage_cap: float, reserve: float = 0.0) -> float:
    """Timeout for the next call: its own cap, but never more than what is left of the caller's deadline."""
    if "no-deadline-propagation" in MUT:
        return stage_cap
    return max(0.0, min(stage_cap, parent_remaining - reserve))


def pipeline_worst_case(stage_caps: list[float], deadline: float) -> float:
    """Worst-case total time when every stage uses its whole timeout."""
    remaining, used = deadline, 0.0
    for cap in stage_caps:
        t = child_timeout(remaining, cap)
        used += t
        remaining -= t
    return used


def apply_once(store: dict[str, str], key: str, action: "callable") -> str:  # type: ignore[valid-type]
    """Run a side effect at most once per idempotency key; a retry returns the first result."""
    if key in store and "idempotency-bypassed" not in MUT:
        return store[key]
    store[key] = action()
    return store[key]


# ---------------------------------------------------------------- checks
POLICIES = {
    "none": Policy("none"),
    "immediate x3": Policy("immediate x3", max_retries=3, backoff="none"),
    "exp backoff x3": Policy("exp backoff x3", max_retries=3, backoff="exp"),
    "full jitter x3": Policy("full jitter x3", max_retries=3, backoff="jitter"),
    "jitter + budget 10%": Policy("jitter + budget 10%", max_retries=3, backoff="jitter", budget=0.1),
    "+ shedding, bounded queue": Policy("+ shedding, bounded queue", max_retries=3, backoff="jitter", budget=0.1,
                                        shed_expired=True, queue_cap=CAP * TIMEOUT),
    "+ circuit breaker": Policy("+ circuit breaker", max_retries=3, backoff="jitter", budget=0.1, shed_expired=True,
                                queue_cap=CAP * TIMEOUT, breaker=True),
}


def check_policies() -> dict[str, Result]:
    res = {name: simulate(p) for name, p in POLICIES.items()}
    none, imm, exp, jit = res["none"], res["immediate x3"], res["exp backoff x3"], res["full jitter x3"]
    bud, shed, brk = res["jitter + budget 10%"], res["+ shedding, bounded queue"], res["+ circuit breaker"]
    # baseline: without any failure the system is healthy (70% utilisation, nobody times out)
    assert none.amplification == 1.0
    # retries add load exactly when the dependency can least afford it
    assert imm.amplification > 1.5 and imm.amplification > jit.amplification > bud.amplification, [r.amplification for r in res.values()]
    assert bud.amplification <= 1.15, bud.amplification
    # the unbounded FIFO queue keeps serving clients that already gave up: wasted work
    assert none.wasted > 0 and imm.wasted > none.wasted
    # recovery: naive immediate retries are worse than no retries; a budget plus shedding is far better than both
    assert imm.recovery_tick is None or none.recovery_tick is None or imm.recovery_tick > none.recovery_tick
    assert shed.recovery_tick is not None and shed.recovery_tick <= 3, shed.recovery_tick
    assert none.recovery_tick is None or shed.recovery_tick < none.recovery_tick
    assert shed.peak_queue <= CAP * TIMEOUT and shed.peak_queue < imm.peak_queue
    # brown-out success: shedding and the bound keep serving fresh requests
    assert shed.success_in_brownout > none.success_in_brownout
    assert brk.recovery_tick is not None and brk.amplification <= bud.amplification + 0.05
    # the breaker sheds load on the dependency (fewer attempts reach it) at the price of rejecting more fresh requests
    assert brk.attempts < shed.attempts and brk.success_in_brownout < shed.success_in_brownout
    # jitter exists to desynchronise a herd that fails together: same retry count, far smaller single-tick spike
    assert herd_peak(POLICIES["full jitter x3"]) < 0.5 * herd_peak(POLICIES["exp backoff x3"]), (
        herd_peak(POLICIES["full jitter x3"]), herd_peak(POLICIES["exp backoff x3"]))
    assert herd_peak(POLICIES["exp backoff x3"]) == 1000
    assert exp.recovery_tick is None or exp.recovery_tick <= imm.recovery_tick if imm.recovery_tick is not None else True
    return res


def check_deadlines_and_idempotency() -> dict[str, float]:
    # three stages whose individual timeouts (4 s each) exceed the caller's 6 s deadline
    assert pipeline_worst_case([4, 4, 4], 6.0) == 6.0, "propagated deadlines cap the worst case at the caller's deadline"
    assert child_timeout(1.5, 4.0) == 1.5 and child_timeout(0.0, 4.0) == 0.0 and child_timeout(10.0, 4.0) == 4.0
    assert child_timeout(5.0, 4.0, reserve=2.0) == 3.0, "a reserve for the caller's own work is kept back"
    store: dict[str, str] = {}
    calls: list[int] = []
    for _ in range(3):  # three retries of the same logical request
        apply_once(store, "job-42", lambda: calls.append(1) or "done")
    assert len(calls) == 1, "a retried side effect must run once per idempotency key"
    return {"worst_case_with": pipeline_worst_case([4, 4, 4], 6.0), "worst_case_without": 12.0}


def run_checks() -> dict[str, object]:
    return {"policies": check_policies(), "deadlines": check_deadlines_and_idempotency()}


def main() -> None:
    r = run_checks()
    print(f"{'policy':28} {'amplif.':>8} {'peak q':>7} {'ok in brown-out':>16} {'wasted':>7} {'recovery (ticks)':>17}")
    for name, x in r["policies"].items():  # type: ignore[union-attr]
        rec = "not within horizon" if x.recovery_tick is None else str(x.recovery_tick)
        print(f"{name:28} {x.amplification:8.2f} {x.peak_queue:7d} {x.success_in_brownout:16.1%} {x.wasted:7d} {rec:>17}")
    print("deadline propagation worst case (3 stages x 4 s, 6 s deadline):", r["deadlines"])
    print("OK: all assertions hold (a simple model with my chosen parameters; no real system measured).")


MUTANT_NAMES = ["no-backoff", "no-jitter", "budget-ignored", "shedding-disabled", "breaker-never-opens",
                "no-deadline-propagation", "idempotency-bypassed"]


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
    if survived:
        print("SURVIVED:", survived)
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
