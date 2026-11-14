"""Smoke-test the public Next.js port of a disposable local demo (no external calls)."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def smoke(port: int) -> None:
    base = f"http://127.0.0.1:{port}"
    cookie = ""

    def api(path, payload=None):
        nonlocal cookie
        headers = {"Content-Type": "application/json", "Cookie": cookie}
        with urlopen(
            Request(
                base + "/api/" + path,
                data=json.dumps(payload).encode() if payload is not None else None,
                headers=headers,
            ),
            timeout=30,
        ) as response:
            if path == "games":
                issued = response.headers["Set-Cookie"]
                assert "secure" in issued.lower() and "httponly" in issued.lower()
                cookie = issued.split(";", 1)[0]
            return json.load(response)

    assert api("health")["status"] == "ok"
    for path in ("/", "/trainer", "/analyzer", "/training"):
        with urlopen(base + path, timeout=30) as r:
            html = r.read().decode()
            assert 'href="/account"' not in html and "Skip to workspace" in html
    try:
        api("account/me")
    except HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("Account endpoint exposed")
    state = api("games", {})
    assert len(state["players"]) == 6 and api("game")["hand_id"] == state["hand_id"]
    api(
        "game/actions",
        {"action": "fold", "hand_id": state["hand_id"], "revision": state["revision"]},
    )
    assert api("analyzer/replay", api("analyzer/trainer"))
    scenarios = api("strategy/scenarios")["scenarios"]
    root = next(s for s in scenarios if s["solution_id"] == "ts-root-v1")
    assert (
        api("strategy/query", {"scenario": root["scenario"]})["status"] == "available"
    )
    assert (
        api("profiles")
        and api(
            "observations/report",
            {"archive": {"version": "1.0", "entries": [], "overrides": {}}},
        )
        == []
    )
    assert (
        api(
            "equity/hand-vs-hand",
            {
                "hero_cards": ["As", "Ah"],
                "opponent_cards": ["Ks", "Kh"],
                "board": ["2c", "3d", "7h", "8c", "Jd"],
            },
        )["players"][0]["equity"]
        == 1
    )
    prompt = next(
        p
        for p in api("strategy/training/exercises")
        if p["solution_id"] == "ts-root-v1" and p["combo"] == "KhQh"
    )
    submission = {
        k: prompt[k] for k in ("solution_id", "scenario_id", "version", "combo")
    }
    submission.update(action="bet@275", hypothesis={"name": "TAG", "profile": "tag"})
    feedback = api("strategy/training/grade", submission)
    assert abs(feedback["loss"] - 120.574177) < 0.000001
    attempt = dict(
        id=str(uuid4()),
        session=str(uuid4()),
        time="2026-01-01T00:00:00Z",
        origin="practice",
        retry=False,
        submission=submission,
        feedback=feedback,
        street=prompt["street"],
        position=prompt["position"],
    )
    assert (
        api("strategy/training/report", {"version": "1", "attempts": [attempt]})[
            "report"
        ]["Model"]["graded"]
        == 1
    )
    print("Guest workflows passed through the public frontend port")


if __name__ == "__main__":
    smoke(int(sys.argv[1]))
