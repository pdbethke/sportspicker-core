"""
A hand-run mutation dry-run over sportspicker_core.

    python scripts/mutation_dryrun.py

Plants goal-violating changes by hand, runs the core suite against each, and
reports killed versus survived. Survivors are the useful output: branches the
tests assert too loosely.

Why it exists: it is cheap insurance before spending an LLM audit. A real
`corral certify --local` run costs tokens and reports a kill-rate; this
answers "would we pass?" for free, and the first run found a genuine gap: the
sport-module fallback was covered only by tests that stayed behind in the
application this library was extracted from, so this suite never touched it.

Two of the mutants below were not written by hand at all. An adversarial
generator planted them during a real audit and this suite let both through —
a single-round contest paying nothing, and a field landing exactly on
min_participants being treated as short of it. They are here now because the
point of this file is to hold what we have learned the tests must defend, and
what we learn that way is exactly what nobody thought to plant.

What it is NOT: an independent audit. The mutants below are ones I thought of
while writing the tests, so a perfect score here says the tests cover the
failures I imagined. An adversarial generator will plant things I did not
imagine, and that is the point of running the real thing.

Every mutant is reverted before the next, and the tree is restored on the way
out even if the suite raises.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (file, goal violated, original snippet, mutated snippet)
MUTANTS = [
    (
        "sportspicker_core/awards.py",
        "pot exactness: an all-zero field silently forfeits its pot",
        "            points = even_split",
        "            points = 0.0",
    ),
    (
        "sportspicker_core/awards.py",
        "pot exactness: shares no longer normalise, so the pot is not respected",
        "            points = (weight / total_weight) * pot_after_minimum",
        "            points = weight * pot_after_minimum",
    ),
    (
        "sportspicker_core/awards.py",
        "the baseline stops bypassing budgets, so it measures nothing",
        "        if is_baseline:\n            points = score.raw_points",
        "        if False:\n            points = score.raw_points",
    ),
    (
        "sportspicker_core/awards.py",
        "competition ranking becomes sequential, so ties are ordered arbitrarily",
        "        if score.raw_points != previous:\n            rank = index + 1\n            previous = score.raw_points",
        "        rank = index + 1\n        previous = score.raw_points",
    ),
    (
        "sportspicker_core/awards.py",
        "ranking inverted: the worst score places first",
        "    ordered = sorted(scores, key=lambda s: s.raw_points, reverse=True)",
        "    ordered = sorted(scores, key=lambda s: s.raw_points)",
    ),
    (
        "sportspicker_core/awards.py",
        "min_participants counts pickers rather than scorers",
        "    scoring = sum(1 for s in scores if s.raw_points > 0)",
        "    scoring = len(scores)",
    ),
    (
        "sportspicker_core/awards.py",
        "min_participants void and scale swapped",
        '    return 0.0 if mode == "void" else pot * (scoring / minimum)',
        '    return pot * (scoring / minimum) if mode == "void" else 0.0',
    ),
    (
        "sportspicker_core/awards.py",
        "an empty contest divides by zero instead of awarding nothing",
        "    if round_count <= 0:\n        return 0.0",
        "    if round_count < 0:\n        return 0.0",
    ),
    (
        "sportspicker_core/awards.py",
        "pot exactness: a single-round contest pays nothing at all",
        "    if round_count <= 0:\n        return 0.0",
        "    if round_count <= 1:\n        return 0.0",
    ),
    (
        "sportspicker_core/awards.py",
        "a field exactly on min_participants is treated as short of it",
        "    if scoring >= minimum:",
        "    if scoring > minimum:",
    ),
    (
        "sportspicker_core/strategies/builtin.py",
        "tied members no longer share the combined value of their positions",
        "            for score in tied:\n                weights[score.membership_id] = pot / len(tied)",
        "            for score in tied:\n                weights[score.membership_id] = pot",
    ),
    (
        "sportspicker_core/strategies/builtin.py",
        "places beyond the points table score full marks instead of the tail",
        "            return float(table[position]) if position < len(table) else tail",
        "            return float(table[position]) if position < len(table) else float(table[0])",
    ),
    (
        "sportspicker_core/strategies/builtin.py",
        "equal weighting credits members who did not score",
        '        return {s.membership_id: (1.0 if s.raw_points > 0 else 0.0) for s in scores}',
        '        return {s.membership_id: 1.0 for s in scores}',
    ),
    (
        "sportspicker_core/engines/binary.py",
        "a drawn match no longer credits everyone",
        "        if is_tie:",
        "        if False:",
    ),
    (
        "sportspicker_core/engines/binary.py",
        "the tiebreaker becomes signed, so overshooting beats undershooting",
        "            tiebreaker_score = (\n                abs(pick.predicted_home_score - home_score)\n                + abs(pick.predicted_away_score - away_score)\n            )",
        "            tiebreaker_score = (\n                (pick.predicted_home_score - home_score)\n                + (pick.predicted_away_score - away_score)\n            )",
    ),
    (
        "sportspicker_core/engines/mma.py",
        "a jackpot pays the same as a single bonus",
        "        if correct_method and correct_round:\n            points = 5  # Jackpot",
        "        if correct_method and correct_round:\n            points = 2  # Jackpot",
    ),
    (
        "sportspicker_core/engines/mma.py",
        "TKO stops being treated as KO, so correct method picks score less",
        '        if method in ("ko", "tko", "ko/tko"):\n            return "ko"',
        '        if method in ("ko", "ko/tko"):\n            return "ko"',
    ),
    (
        "sportspicker_core/registry.py",
        "an unregistered sport no longer falls back to binary scoring",
        "        return self.get(slug).engine or self._default_engine",
        "        return self.get(slug).engine",
    ),
]


def run_suite() -> bool:
    """True when the core suite passes."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests_core", "-q", "-x", "-p", "no:warnings"],
        cwd=REPO, capture_output=True, text=True,
    )
    return result.returncode == 0


def main():
    killed, survived = [], []

    for path, goal, original, mutated in MUTANTS:
        target = REPO / path
        source = target.read_text()
        if original not in source:
            print(f"SKIP  (snippet not found) {goal}")
            continue

        target.write_text(source.replace(original, mutated, 1))
        try:
            passed = run_suite()
        finally:
            target.write_text(source)

        if passed:
            survived.append((path, goal))
            print(f"SURVIVED  {goal}")
        else:
            killed.append((path, goal))
            print(f"killed    {goal}")

    total = len(killed) + len(survived)
    print(f"\nkill rate: {len(killed)}/{total} = {len(killed) / total:.2f}")
    if survived:
        print("\nsurvivors — branches the tests assert too loosely:")
        for path, goal in survived:
            print(f"  {path}: {goal}")


main()
