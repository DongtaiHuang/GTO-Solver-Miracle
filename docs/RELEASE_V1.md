# MIRACLE v1.0 release candidate

**Status: Stage 1 preparation.** No public URL, production acceptance record, tag or release has been issued in this stage.

Next.js/React/TypeScript presents Study, Trainer, Hand Analyzer, Training Center and Player Account. FastAPI hosts an independent integer-chip six-player NLHE engine, deterministic replay, numerical services and owner-scoped persistence. PostgreSQL, SQLAlchemy, Alembic and Google identity tokens support private saves. Guest games remain ephemeral; tab archives require explicit import or export.

Study has 37 reviewed decision records: four restricted river decisions from Task 006A, five expanded river decisions from Task 008, and 28 published turn-to-river decisions from Task 009. CFR+ turn optimization integrates all 44 legal river cards per compatible deal. The published subset does not cover arbitrary hands, ranges, boards or bet sizes. Unsupported decisions stay ungraded. Showdown equity, equilibrium action EV and best response to an explicit opponent policy have different meanings. [Joint solver](TASK009.md) · [Conditional models](TASK011.md) · [Practice grading](TASK012.md)

**Prior evidence:** Task 014C passed 354 backend tests (98.06% combined coverage), 54 frontend tests, 12 numerical tests, TypeScript, a production build and 20 targeted Chromium tests locally. Its PR passed all six CI jobs. Task 014A exercised PostgreSQL 16.2 migration, process restart and native restore; Task 014B used locally signed test tokens. These results establish candidate behavior, not live Google authentication or public readiness. [014A](TASK014A.md) · [014B](TASK014B.md) · [014C](TASK014C.md)

## Stage 2 acceptance record (all pending)

- [ ] Record authorized commit, image digests, provider, region, public URL, timestamp and reviewer. Verify migration, /health, /ready and public-to-private proxy connectivity.
- [ ] On public HTTPS open all five routes. Play a guest hand, settle and reopen it in Analyzer. Query a supported and an unsupported Study scenario. Grade and retry a training attempt; confirm the exact-combo Study link.
- [ ] Use two real Google test accounts. Check exact origin, successful login, Secure/HttpOnly/SameSite session, expiration and logout. Explicitly save and reopen a hand and training session on another device. Verify the other account cannot see those fixtures.
- [ ] Confirm database trusted sources, TLS certificate validation, encrypted backups and retention. Restore to an isolated empty target, compare owner-scoped data, invalidate restored sessions/challenges and document recovery time.
- [ ] Verify host/origin restrictions, rejected cross-origin mutations, ingress throttles and body limits. Inspect representative redacted logs; scan final dependency versions/images and check backup access and secrets rotation.
- [ ] Exercise maintenance and rollback with prior compatible images or a separately restored database. Record recovery point, accepted data-loss window and operator approval.
- [ ] Resolve critical failures and attach redacted evidence to the release review. Retain unresolved physical-device, accessibility and load limitations. Obtain separate approval for publication and tagging.
