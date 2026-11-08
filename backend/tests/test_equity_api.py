from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

import poker_lab.equity_api as api
from poker_lab.api import create_app

BOARD = ["2c", "3d", "7h", "8c", "Jd"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_all_typed_equity_routes_and_private_responses(client: TestClient) -> None:
    cases = [
        ("hand-vs-hand", {"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"]}),
        ("hand-vs-range", {"hero_cards": ["As", "Ah"], "opponent_range": {"weights": {"KK": 100}}}),
        (
            "range-vs-range",
            {"hero_range": {"weights": {"AA": 100}}, "opponent_range": {"weights": {"KK": 100}}},
        ),
        ("multiway", {"players": [{"cards": ["As", "Ah"]}, {"range": {"weights": {"KK": 100}}}]}),
    ]
    for route, payload in cases:
        response = client.post("/api/equity/" + route, json={**payload, "board": BOARD})
        assert response.status_code == 200, response.text
        assert response.json()["players"][0]["equity"] == 1
        assert response.json()["method"] == "exact"
        assert "no-store" in response.headers["cache-control"]
    sampled = client.post(
        "/api/equity/hand-vs-hand",
        json={
            "hero_cards": ["As", "Ah"],
            "opponent_cards": ["Ks", "Kh"],
            "samples": 100,
            "seed": 7,
        },
    )
    assert sampled.json()["valid_samples"] == 100
    assert (
        sampled.json()["players"][0]["uncertainty"]["interval_method"]
        == "hoeffding_95_simultaneous"
    )
    result = client.post("/api/equity/pot-odds", json={"pot": 300, "call": 100, "equity": 0.4})
    assert result.status_code == 200 and result.json()["call_ev"] == 60


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"hero_cards": ["As", "As"], "opponent_cards": ["Ks", "Kh"]}, 400),
        ({"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "board": ["2c", "3d"]}, 400),
        ({"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "samples": 10001}, 422),
        ({"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "samples": True}, 422),
        ({"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "seed": -1}, 422),
        ({"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "method": "exact"}, 422),
        ({"hero_cards": ["As"], "opponent_cards": ["Ks", "Kh"]}, 422),
        (
            {"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "profile": "standard_gto"},
            422,
        ),
    ],
)
def test_validation_and_work_limits(client: TestClient, payload: dict, status: int) -> None:
    assert client.post("/api/equity/hand-vs-hand", json=payload).status_code == status


@pytest.mark.parametrize("player", [{}, {"cards": ["As", "Ah"], "range": {"weights": {"AA": 100}}}])
def test_player_spec_requires_one_kind(client: TestClient, player: dict) -> None:
    assert (
        client.post(
            "/api/equity/multiway", json={"players": [player, {"cards": ["Ks", "Kh"]}]}
        ).status_code
        == 422
    )


def test_invalid_ranges_player_counts_and_pot_values(client: TestClient) -> None:
    for count in (1, 7):
        response = client.post(
            "/api/equity/multiway", json={"players": [{"range": {"weights": {"AA": 100}}}] * count}
        )
        assert response.status_code == 422
    for weights, status in (
        ({}, 400),
        ({"AA": 101}, 422),
        ({"KK": 50.5}, 422),
        ({"nope": 100}, 422),
    ):
        assert (
            client.post(
                "/api/equity/hand-vs-range",
                json={
                    "hero_cards": ["As", "Ah"],
                    "opponent_range": {"weights": weights},
                },
            ).status_code
            == status
        )
    assert (
        client.post("/api/equity/pot-odds", json={"pot": 0, "call": 0, "equity": 0.5}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/equity/pot-odds", json={"pot": 100, "call": 10.5, "equity": 0.5}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/equity/pot-odds", json={"pot": 100, "call": 10, "equity": 1.1}
        ).status_code
        == 422
    )


def test_one_active_calculation_per_process_without_blocking_the_api(
    client: TestClient, monkeypatch
) -> None:
    entered, release = Event(), Event()
    real = api.calculate_equity

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "calculate_equity", blocked)
    payload = {"hero_cards": ["As", "Ah"], "opponent_cards": ["Ks", "Kh"], "board": BOARD}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/api/equity/hand-vs-hand", json=payload)
        try:
            assert entered.wait(10)
            assert client.post("/api/equity/hand-vs-hand", json=payload).status_code == 429
            assert client.get("/health").status_code == 200
        finally:
            release.set()
        assert pending.result().status_code == 200
    assert client.post("/api/equity/hand-vs-hand", json=payload).status_code == 200
