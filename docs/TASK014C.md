# Task 014C — Workspace QA and orange branding

The README uses a proportional 720 × 240 PNG derived from the approved GTO-Solver-Miracle Orange Spade Logo.png. The small navigation mark and favicon share a 96 × 96 crop of the spade, including its grid, rising arrow and surrounding white margin. Both assets live in frontend/public/brand. The wordmark has alternative text; the navigation icon is decorative beside the MIRACLE home-link text.

| Workspace | Change and acceptance coverage |
|---|---|
| Study | The return link from Training Center carries the exact solution, public scenario and Hero combo. Querying the matching validated strategy restores the corresponding matrix class and combo details. Browser tests cover keyboard matrix selection, unavailable states, genuine solver results and mobile equity workspace access. |
| Trainer | Custom bet sizing identifies the legal total-street range and exposes invalid input to assistive technology. Existing full-hand, fold, settlement and Trainer-to-Analyzer tests passed. |
| Hand Analyzer | Schema errors identify recognized fields and omit submitted values. Browser coverage includes manual entry, malformed imports, replay and private-card visibility. |
| Training Center | A mobile exercise test checks model-conditioned EV loss, retries, persistence and the round trip to the same exact combination in Study. Equilibrium and model grading continue to use their separate benchmarks. |
| Player Account | Initial identity lookup has a distinct loading state. The mocked account test imports a named tab save, reopens the saved record in the real Analyzer, verifies the seat name, merges training history, exports evidence and signs out. |

All five destinations share active navigation. A keyboard skip link focuses the workspace directly. The compact navigation wraps on smaller screens; links have a visible focus indicator and a 44px minimum height there. Browser tests followed all five routes at 390, 768 and 1440 CSS pixels, checked document width and exercised back/forward history.

## Local verification

Heavy checks ran sequentially. All 54 frontend tests, TypeScript, 354 backend tests (98.06% combined coverage, including the disposable PostgreSQL account suite), 12 numerical solver tests and the production frontend build passed. Twenty targeted Chromium Playwright tests passed against that build. No backend, security, solver or dataset files changed. Mock identity flows do not verify live Google sign-in. The complete browser suite, Docker jobs, physical touch devices and screen-reader behavior were outside this local pass.
