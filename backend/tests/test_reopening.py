from poker_lab.engine import Holdem
from poker_lab.models import Action, Street


def test_check_retains_raise_right_against_short_opening_all_in() -> None:
    game = Holdem(seats=3, stacks=[150, 1000, 1000])
    game.act(0, "call")
    game.act(1, "call")
    game.act(2, "check")
    assert game.street == Street.FLOP
    game.act(1, "check")
    game.act(2, "check")
    game.act(0, "all_in")
    assert game.current_bet == 50
    assert Action.RAISE in game.legal_actions().actions
    assert game.legal_actions().min_raise_to == 150
    game.act(1, "raise", 150)
    assert Action.RAISE in game.legal_actions().actions
