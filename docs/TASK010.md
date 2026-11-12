# Task 010 — Adaptive opponent observations

Expand **Opponent observations** on Trainer, Analyzer, or Study. Trainer captures the public betting history of a completed hand automatically. Analyzer accepts explicitly mapped players from a validated hand. Study reads the same tab's archive. Open **Recorded evidence** to inspect each hand reference, position, starting stack, actions and contributed successes/trials. The learning system uses betting decisions only.

## Architecture and identity

The Trainer's existing opaque session cookie controls its active game. Completed create/get/action responses now include an optional observation packet produced from the authorized public GameView. All cards in the six seat records and all payouts are removed before the packet is stored. The application reuses Analyzer's action/amount conventions and replay function. The ordinary Trainer and Analyzer still show legitimately visible cards under their existing rules.

Each physical Trainer seat has a stable bot ID across button rotations (bot-1 through bot-5). Hero has trainer-hero. A bot's history can span different configured heuristics; the source label is Trainer. On a completed response the browser records that hand ID once. Reloading the same hand is idempotent. A last-seen receipt also prevents immediately resurrecting the current completed hand after reset or deletion. Trainer exports carry an optional trainer_hand_id, including when saved and reopened in Analyzer. Direct trainer reviews cannot be added as manual hands.

For a manual hand, validate or import application hand JSON, expand **Add this hand to opponent observations**, provide a stable hand reference, and map each desired position to a new or existing manual identity. Unmapped seats are skipped in the report, though their actions are needed for reconstructing the betting sequence. Reuse the same identity when a person changes positions. Equal names never cause a merge. The displayed name follows the most recently recorded name for that ID. Source attribution for manually supplied files relies on the recorder; imported archives are local data, not authenticated evidence.

The pure backend report rebuilds each hand using Analyzer before accumulating trials. Aggregate statistics, classifications and intervals are derived on demand and are never trusted as imported measurements. The new report endpoint accepts no strategy solution requests, and does not change equilibrium data or the established combo-specific river response policy.

## Metrics

Every table cell shows successes / eligible trials. Only recorded decisions contribute action-based trials. Future streets and responses after a player folds are never filled in.

| Metric | Success | Eligible trial |
|---|---|---|
| VPIP | Any voluntary preflop call or aggression, including an all-in call | One resolved preflop per dealt player |
| PFR | Any preflop raise, including an aggressive short all-in | Same resolved-hand denominator; multiple raises count once |
| 3-bet | Make a full legal re-raise over the opening raise | Each observed preflop decision with one prior raise and a full re-raise legal |
| Fold to 3-bet | Opening raiser folds | Its observed response to a full 3-bet while that wager is still outstanding; intervening calls are allowed, further raises supersede it |
| Flop c-bet | Last preflop aggressor bets | Its observed opportunity to open the flop when betting is legal and no player has yet bet |
| Fold to flop c-bet | Fold to that continuation bet | Each observed response to the qualifying c-bet until a raise or the end of the street |
| Turn / river aggression | Bet or raise, including aggressive all-in | Recorded decisions on that street where an aggressive action is legal |
| Postflop call / fold | Call (including capped all-in call) / fold | Each postflop decision facing a positive call cost; raising counts as neither |

Blinds are forced and never count as voluntary bets. A walk is one resolved preflop for each seat, including a zero for BB. Partial preflop histories count VPIP/PFR only for players already folded or all-in, or once the street/hand is complete. This avoids calling an unresolved hand a negative trial. Known decisions can still contribute 3-bet/c-bet/action trials before the full hand ends. A checked-through limped pot has no preflop aggressor. Multiway pots use the same eligibility rules: checks before the aggressor preserve the c-bet opportunity; a lead removes it. If another player raises a c-bet, players facing that raise do not face the original bet. “Observed hands” counts mapped hand records and can exceed resolved preflop trials.

## Uncertainty and classification

With s successes from n binary trials, observed frequency is s/n. We use a uniform Beta(1,1) prior for each metric; posterior Beta(s+1,n−s+1) has mean (s+1)/(n+2). The 95% equal-tail credible interval uses bisection of the integer-shape beta CDF, evaluated by the binomial-tail identity. For one success in one trial the observed rate is 100%, the posterior mean is 66.7%, and the interval spans approximately 15.8–98.7%. With zero trials the report returns null for frequency, estimate and interval. Twenty trials marks the dashboard sample-size indicator. Real poker decisions are context dependent and correlated; these intervals assume exchangeable binary trials for a particular statistic.

Classification defaults to unknown below 20 resolved preflops or five voluntary hands. Otherwise a VPIP posterior mean of at least 30% is provisionally loose. Among voluntary hands, a raise-participation estimate (PFR successes + 1)/(VPIP successes + 2) of at least 60% is provisionally aggressive. The two axes yield TAG, LAG, TP or LP. The report gives measured evidence and thresholds. The report request can configure minimum_hands, loose_threshold and aggressive_threshold in rules. Postflop evidence is displayed separately because many small datasets have too few eligible postflop decisions. These conventions have no population calibration. Standard GTO is exclusively a selectable benchmark.

A manual override is a separate label and leaves the inferred label and evidence visible. Before the next Trainer deal, explicitly adopting an eligible bot's provisional label selects that existing archetype's default heuristic preset. Standard GTO and manually configured seats remain selectable in the ordinary configuration drawer. Active-hand settings are frozen. VPIP and PFR cannot identify private-combo river betting probabilities. Study's solver comparisons and conditional best responses continue to use their own exact game and action-policy assumptions.

## Persistence, API and limits

The archive is JSON version 1.0 with entries and overrides. Each entry contains hand_id, source (trainer or manual), mapping (position → identity ID), and a card-redacted version 1.0 Analyzer hand. IDs are 1–80 ASCII letters, numbers, underscores or hyphens. Overrides map known identity IDs to one of the four archetypes. The export preserves the original evidence used in the report. Re-import replaces the current archive after validation and explicit confirmation.

POST /api/observations/report accepts {archive, rules?} and returns per-identity reports. No server-side archive or list of other users' observations exists. No account or cloud synchronization is required. The existing Trainer session owner receives the finished game packet. The browser stores observations in sessionStorage, shared by pages of that tab. A duplicated tab may inherit an initial copy. Closing a tab usually clears it; export for durable storage. People with access to exported JSON can read its names and betting history.

Limits: 128 hands, 4,096 total actions, six mapped seats per hand, 1 MB local file/storage cap and 1 MiB report request cap. Reject unknown fields, invalid cards in archives (all seat cards must be null), payouts, duplicate IDs, repeated mappings, incompatible sources, unknown override IDs and illegal replay events. Manual duplicate-content detection also ignores display names, hero designation and redundant initial pot; two distinct manual hands with identical public data cannot be distinguished by that check. Distinct server-issued Trainer hand IDs can legitimately contain identical sequences. Use stable manual references even for partial hands; this milestone does not merge partial hand revisions automatically. Deleting a player drops its mapping and override and removes empty hand records. Shared public action context remains for other players in that hand. Reset clears the whole archive. Imported source labels are declarations within the user's own tab. There is no site text parser or population dataset.

## Reproduce

Follow README's Python 3.12 and Node setup. Run pytest, Ruff and mypy in backend; run python -m pytest -q tools, npm test, npm run typecheck, npm run build and npm run test:e2e from the root. Browser tests exercise completed Trainer capture, reload deduplication, explicit preset adoption, Study inspection, Analyzer mapping, overrides, export/import, deletion and reset. Backend tests include multiway and incomplete histories, capped all-ins, opportunity denominators, identity across positions, analytical beta quantiles and session ownership. Synthetic hands used in tests are never shipped as observations.
