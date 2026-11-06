import pytest

from poker_lab.evaluator import evaluate


@pytest.mark.parametrize(
    "cards,expected",
    [
        ("As Ks Qs Js Ts 2d 3c", (8, 14)),
        ("As 2s 3s 4s 5s Kd Qh", (8, 5)),
        ("Ac Ad Ah As Kd Qc 2d", (7, 14, 13)),
        ("Ac Ad Ah Kc Kd Kh 2d", (6, 14, 13)),
        ("As Js 9s 7s 4s 3s 2d", (5, 14, 11, 9, 7, 4)),
        ("Ac 2d 3s 4h 5c Kd Qc", (4, 5)),
        ("9c Td Js Qh Kc Ad 2c", (4, 14)),
        ("Ac Ad Ah Kc Qd 9h 2d", (3, 14, 13, 12)),
        ("Ac Ad Kc Kd Qc Qd 2h", (2, 14, 13, 12)),
        ("Ac Ad Kc Qd Jh 9s 2d", (1, 14, 13, 12, 11)),
        ("Ac Kd Qc Jh 9s 7d 2h", (0, 14, 13, 12, 11, 9)),
    ],
)
def test_exact_ranks(cards: str, expected: tuple[int, ...]) -> None:
    assert evaluate(cards.split()) == expected


def test_category_order_and_kickers() -> None:
    hands = [
        "Ac Kd Qc Jh 9s 7d 2h",
        "Ac Ad Kc Qd Jh 9s 2d",
        "Ac Ad Kc Kd Qc Qd 2h",
        "Ac Ad Ah Kc Qd 9h 2d",
        "Ac 2d 3s 4h 5c Kd Qc",
        "As Js 9s 7s 4s 3s 2d",
        "Ac Ad Ah Kc Kd Kh 2d",
        "Ac Ad Ah As Kd Qc 2d",
        "As Ks Qs Js Ts 2d 3c",
    ]
    ranks = [evaluate(h.split()) for h in hands]
    assert ranks == sorted(ranks)
    assert evaluate(["Ac", "Ad", "Kc", "Qd", "Jh", "9s", "2d"]) > evaluate(
        ["Ah", "As", "Kd", "Qc", "Th", "8s", "2c"]
    )


@pytest.mark.parametrize("cards", [["As"] * 7, ["As"], ["XX"] * 7])
def test_invalid_cards(cards: list[str]) -> None:
    with pytest.raises(ValueError):
        evaluate(cards)
