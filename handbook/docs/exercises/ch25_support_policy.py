"""Chapter 25 exercise: decision policy for a customer-support RAG bot (stdlib only).

A public-facing support bot decides, per conversation, whether to answer or hand off to a human. This simulation
(SYNTHETIC traffic and user behaviour, parameters are MY CHOICES) shows:

  A. why "containment" (no human involved) overstates "resolution" (the customer's problem was solved), measured
     under three definitions that mirror the contained / reopened / verified distinction vendors use (S177);
  B. the answer-or-escalate threshold as a cost trade-off, with a U-shaped total cost and an interior optimum;
  C. deterministic guards that do not depend on the model: high-risk intents always go to a human; a commitment
     (refund, guarantee, entitlement) may only be stated if it is quoted verbatim from a cited policy passage
     (the failure in the Air Canada chatbot case, S176); the first message discloses that the user is talking to AI;
  D. a mutation check.

Run: python -I docs/exercises/ch25_support_policy.py [--mutants]
Nothing here measures a real bot, real customers or real costs. Costs are abstract units. The calibration of the
bot's confidence (P(correct) = confidence for answerable questions) is an ASSUMPTION; real retrieval confidence
is usually worse calibrated, which makes every conclusion about thresholds optimistic.
"""
from __future__ import annotations

import random
import re
import sys
from dataclasses import dataclass

MUT: set[str] = set()

# intent: (share of traffic, high risk, probability the knowledge base can answer it)
INTENTS = {
    "faq": (0.35, False, 0.92),
    "order_status": (0.25, False, 0.90),
    "policy": (0.20, False, 0.75),
    "refund": (0.12, True, 0.70),
    "legal_safety": (0.08, True, 0.50),
}
C_HUMAN, C_COMPLAINT, C_BOT = 5.0, 50.0, 0.1   # abstract cost units


# ---------------------------------------------------------------- C. deterministic guards
_PROMISE = re.compile(r"(?i)\b(we will refund|you(?:'re| are) entitled|we guarantee|guaranteed|full refund|you can apply retroactively|within \d+ days)\b")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def commitment_guard(answer: str, cited_policy: str) -> bool:
    """True if the answer may be sent. A sentence containing a commitment must appear VERBATIM (after whitespace
    and case normalisation) in the cited policy passage; otherwise the answer is blocked and the conversation
    goes to a human. Verbatim is deliberately strict: it cannot be fooled by a negation the way word overlap can."""
    if "guard-off" in MUT:
        return True
    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        if _PROMISE.search(sentence):
            ok = _norm(sentence) in _norm(cited_policy) if "guard-substring-words" not in MUT else all(w in _norm(cited_policy) for w in _norm(sentence).split())
            if not ok:
                return False
    return True


def first_message_ok(text: str) -> bool:
    """The first bot message must say, clearly and before anything else, that the user is talking to an AI system."""
    if "no-disclosure" in MUT:
        return True
    return bool(re.search(r"(?i)\b(AI|artificial intelligence|automated assistant|virtual assistant)\b", text[:200]))


# ---------------------------------------------------------------- the simulation
@dataclass
class Outcome:
    n: int = 0
    answered: int = 0
    escalated_upfront: int = 0
    correct: int = 0
    wrong_abandon: int = 0
    wrong_reopen: int = 0
    wrong_complaint: int = 0
    high_risk_answered: int = 0
    blocked_by_guard: int = 0

    # three ways to call a conversation "resolved by the bot"
    def containment(self) -> float:                 # no human involved at the time the conversation ends
        return (self.answered if "containment-counts-escalations" not in MUT else self.answered + self.escalated_upfront) / self.n

    def no_reopen(self) -> float:                   # contained and the customer did not come back
        return (self.correct + self.wrong_abandon + self.wrong_complaint) / self.n

    def verified(self) -> float:                    # the answer was actually correct (ground truth known only in simulation)
        return self.correct / self.n

    def complaints(self) -> float:
        return self.wrong_complaint / self.n

    def cost(self) -> float:
        humans = self.escalated_upfront + self.wrong_reopen
        return (C_HUMAN * humans + C_COMPLAINT * self.wrong_complaint + C_BOT * self.answered) / self.n


def simulate(tau: float, n: int = 6000, seed: int = 7, answer_high_risk: bool = False) -> Outcome:
    rng = random.Random(seed)
    out = Outcome()
    names, shares = list(INTENTS), [INTENTS[k][0] for k in INTENTS]
    for _ in range(n):
        out.n += 1
        intent = rng.choices(names, shares)[0]
        _, high, p_ans = INTENTS[intent]
        answerable = rng.random() < p_ans
        conf = min(1.0, max(0.0, rng.gauss(0.78 if answerable else 0.42, 0.15)))
        wants_to_answer = conf >= tau
        if high and not (answer_high_risk or "high-risk-not-escalated" in MUT):
            wants_to_answer = False                      # high-risk intents always go to a human
        if not wants_to_answer:
            out.escalated_upfront += 1
            continue
        correct = answerable and rng.random() < conf     # ASSUMPTION: calibrated confidence
        has_commitment = rng.random() < (0.30 if intent in {"refund", "policy"} else 0.05)
        supported = has_commitment and correct           # a correct answer's commitment is quotable from the policy
        draft = "We will refund the full fare." if has_commitment else "Here is how that works."
        cited = "We will refund the full fare." if supported else "Refunds are not available after travel."
        if not commitment_guard(draft, cited):
            out.blocked_by_guard += 1
            out.escalated_upfront += 1
            continue
        out.answered += 1
        if high:
            out.high_risk_answered += 1
        if correct:
            out.correct += 1
        else:
            u = rng.random()
            if u < 0.5:
                out.wrong_abandon += 1                   # the customer gives up: looks like containment
            elif u < 0.8:
                out.wrong_reopen += 1                    # comes back to a human
            else:
                out.wrong_complaint += 1                 # harm event
    return out


# ---------------------------------------------------------------- checks
def check_guards() -> None:
    policy = "Bereavement fares cannot be applied retroactively. Requests must be made before travel."
    air_canada_style = "You can apply retroactively within 90 days of travel."
    assert commitment_guard(air_canada_style, policy) is False, "an unsupported commitment must be blocked"
    assert commitment_guard("Bereavement fares cannot be applied retroactively.", policy) is True, "a verbatim quote is allowed"
    assert commitment_guard("Thanks for contacting us. Let me look that up.", policy) is True, "no commitment, no block"
    # word-overlap would be fooled: every word of the wrong sentence appears in the policy text (negation lost)
    tricky = "Bereavement fares can be applied retroactively."
    assert commitment_guard(tricky + " We guarantee it.", policy) is False
    # every word of the wrong sentence appears in the policy ("not available" supplies "available"): word overlap
    # would pass it, verbatim quoting does not
    p2 = "Claims must be filed within 30 days. Refunds are not available after travel."
    inverted = "Refunds are available within 30 days."
    assert commitment_guard(inverted, p2) is False, "an inverted commitment must not pass on word overlap"
    assert commitment_guard("Claims must be filed within 30 days.", p2) is True
    assert first_message_ok("Hi, I'm an AI assistant for Example Air. I can answer questions about fares.")
    assert not first_message_ok("Hi! How can I help you today?")
    assert not first_message_ok("Welcome to Example Air support. " + "x" * 300 + " I am an AI")


def check_resolution_definitions() -> dict[str, float]:
    o = simulate(0.3)
    assert o.containment() >= o.no_reopen() >= o.verified(), (o.containment(), o.no_reopen(), o.verified())
    gap_low = o.containment() - o.verified()
    gap_high = simulate(0.8).containment() - simulate(0.8).verified()
    assert gap_low > gap_high + 0.03, (gap_low, gap_high)
    assert o.containment() > 0.5 and o.verified() < o.containment() - 0.1
    return {"containment": o.containment(), "no_reopen": o.no_reopen(), "verified": o.verified(), "gap": gap_low}


def check_threshold_tradeoff() -> dict[str, object]:
    taus = [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    rows = {t: simulate(t) for t in taus}
    costs = {t: r.cost() for t, r in rows.items()}
    best = min(costs, key=costs.get)  # type: ignore[arg-type]
    assert 0.2 < best < 0.9, (best, costs)
    assert costs[best] < costs[0.0] and costs[best] < costs[0.9]
    # more caution: fewer complaints, more human handoffs
    assert rows[0.8].complaints() < rows[0.2].complaints() and rows[0.8].escalated_upfront > rows[0.2].escalated_upfront
    # a wrong answer that the customer abandons is invisible to the containment metric
    assert rows[0.2].wrong_abandon > 0 and rows[0.2].containment() > rows[0.2].verified()
    return {"best_tau": best, "cost_best": costs[best], "cost_at_0": costs[0.0], "cost_at_0.9": costs[0.9],
            "complaints_at_0.2": rows[0.2].complaints(), "complaints_at_0.8": rows[0.8].complaints()}


def check_high_risk_and_guard_effect() -> dict[str, float]:
    on = simulate(0.5)
    assert on.high_risk_answered == 0, "high-risk intents never reach the bot's answer path"
    assert simulate(0.5, answer_high_risk=True).high_risk_answered > 0
    no_guard_complaints = None
    MUT.add("guard-off")
    try:
        no_guard_complaints = simulate(0.5).complaints()
    finally:
        MUT.discard("guard-off")
    guarded = simulate(0.5).complaints()
    assert guarded < no_guard_complaints, (guarded, no_guard_complaints)
    assert simulate(0.5).blocked_by_guard > 0
    return {"complaints_with_guard": guarded, "complaints_without_guard": no_guard_complaints}


def run_checks() -> dict[str, object]:
    check_guards()
    return {"resolution": check_resolution_definitions(), "tradeoff": check_threshold_tradeoff(), "guards": check_high_risk_and_guard_effect()}


def main() -> None:
    r = run_checks()
    res = r["resolution"]
    print(f"at threshold 0.3: containment {res['containment']:.1%} >= no-reopen {res['no_reopen']:.1%} >= verified {res['verified']:.1%}"  # type: ignore[index]
          f" (containment overstates resolution by {res['gap']:.1%} points)")  # type: ignore[index]
    print("threshold trade-off:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r["tradeoff"].items()})  # type: ignore[union-attr]
    print("guards:", {k: round(v, 4) for k, v in r["guards"].items()})  # type: ignore[union-attr]
    print("OK: all assertions hold (synthetic traffic and assumed calibration; no real bot or customers measured).")


MUTANT_NAMES = ["guard-off", "guard-substring-words", "no-disclosure", "high-risk-not-escalated", "containment-counts-escalations"]


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
