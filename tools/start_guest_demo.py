"""Supervise the two production processes inside the guest-only image."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    port = int(os.environ.get("PORT", "10000"))
    if port == 8000 or not 1 <= port <= 65535:
        raise SystemExit(
            "PORT must be a valid port different from the internal port 8000"
        )
    origin = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("TRAINER_ORIGIN")
    if not origin:
        raise SystemExit("RENDER_EXTERNAL_URL or TRAINER_ORIGIN is required")
    env = {
        **os.environ,
        "MIRACLE_ENV": "guest-demo",
        "COOKIE_SECURE": "true",
        "TRAINER_ORIGIN": origin,
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "BACKEND_URL": "http://127.0.0.1:8000",
        "NODE_ENV": "production",
    }
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node runtime missing")
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "poker_lab.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--workers",
                    "1",
                    "--no-access-log",
                ],
                env=env,
            )
        )
        children.append(
            subprocess.Popen(
                [
                    node,
                    str(ROOT / "node_modules/next/dist/bin/next"),
                    "start",
                    "--hostname",
                    "0.0.0.0",
                    "--port",
                    str(port),
                ],
                cwd=ROOT / "frontend",
                env=env,
            )
        )
        while not stopping and all(p.poll() is None for p in children):
            time.sleep(0.25)
        return 0 if stopping else 1
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    raise SystemExit(main())
