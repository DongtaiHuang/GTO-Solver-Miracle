"""Task 006A terminal utilities in incremental river chips."""

from poker_lab.evaluator import evaluate

BOARD = ["Kd", "7h", "2s", "Tc", "9d"]
POT = 550


def showdown_share(btn: tuple[str, str], bb: tuple[str, str]) -> float:
    left, right = (evaluate(hand + tuple(BOARD)) for hand in (btn, bb))
    return float(left > right) + 0.5 * (left == right)


def called_payoff(share: float, bet: int) -> float:
    return share * (POT + 2 * bet) - bet
