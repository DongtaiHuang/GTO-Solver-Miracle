"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { TrainerRiverFeedback } from "./TrainerRiverFeedback";
import { useProfiles } from "../lib/useProfiles";
import { OpponentSetup, initialOpponents } from "./OpponentSetup";
import type { ProfileConfig } from "../lib/study-types";
import { ApiError, requestGame } from "../lib/api";
import type { Action, GameState } from "../lib/types";
import { ActionControls } from "./ActionControls";
import { HistoryPanel } from "./HistoryPanel";
import { TablePreview } from "./TablePreview";
import { PokerTable } from "./PokerTable";
import { ShowdownResult } from "./ShowdownResult";
import { chips } from "./PlayerSeat";
export function Trainer() {
  const { profiles, error: profileError } = useProfiles();
  const [opponents, setOpponents] = useState<ProfileConfig[]>(initialOpponents);
  const [game, setGame] = useState<GameState | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [needsSync, setNeedsSync] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const current = await requestGame("/api/game");
      setGame(current);
      if (current.opponents?.length === 5) setOpponents(current.opponents.map(p => ({ id: p.id, parameters: p.parameters })));
      setNeedsSync(false); setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setGame(null); setNeedsSync(false); setError("");
      } else {
        setNeedsSync(true); setError(err instanceof Error ? err.message : "Unable to load the table.");
      }
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  async function mutate(path: string, body: unknown) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      setGame(await requestGame(path, body)); setNeedsSync(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete the action.");
      try { setGame(await requestGame("/api/game")); setNeedsSync(false); }
      catch (recovery) {
        if (recovery instanceof ApiError && recovery.status === 404) {
          setGame(null); setNeedsSync(false);
        } else { setNeedsSync(true); }
      }
    } finally { setBusy(false); }
  }
  function act(action: Action, amount?: number) {
    if (game) void mutate("/api/game/actions", {
      hand_id: game.hand_id, revision: game.revision, action, ...(amount === undefined ? {} : { amount }),
    });
  }
  const completed = game?.street === "complete";
  return <main className="trainer practice-room">
    <header className="app-header"><div><p className="eyebrow">6-MAX CASH</p><h1>Trainer</h1></div>
      <div className="header-actions"><span className="practice-badge">Heuristic opponents</span>
        <button className="primary" disabled={busy || needsSync || profiles.length !== 5 || (!!game && !completed)}
          onClick={() => void mutate("/api/games", { opponents })}>New Hand</button></div></header>
    {profileError && <div className="error-banner" role="alert">{profileError}</div>}
    <OpponentSetup profiles={profiles} configs={opponents} onChange={setOpponents}
      disabled={busy || profiles.length !== 5 || (!!game && !completed)} />
    {error && <div className="error-banner" role="alert">{error}
      <button disabled={busy} onClick={() => void refresh()}>Refresh table</button></div>}
    {game ? <>
      <div className="game-metrics"><span className="street-chip">{game.street}</span><span>Hand <b>#{game.hand_number}</b></span><span>Blinds <b>50 / 100</b></span>
        <span>Hero effective <b>{chips(game.effective_stack)} chips</b></span>
        <span aria-live="polite">{busy ? "Processing…" : completed ? "Hand complete" : "Acting: "+(game.players[game.actor??game.hero].name)}</span></div>
      <div className="workspace"><div className="play-area">
        <PokerTable game={game} />
        {completed ? <ShowdownResult game={game} /> :
          <ActionControls key={`${game.hand_id}-${game.revision}`} legal={game.legal}
            disabled={busy || needsSync || game.actor !== game.hero} onAction={act} />}
      </div><HistoryPanel entries={game.history} /></div>
      {game.street==="river" && game.actor===game.hero && <TrainerRiverFeedback key={game.hand_id+game.revision} game={game}/>}
      <div className="trainer-study-link"><Link href="/?from=trainer">Open this hand in Study ↗</Link></div>
      {completed && <p className="session-note">Start a new hand to reset all stacks to 100 BB and rotate the button.</p>}
    </> : <TablePreview opponents={opponents}/>}
    <footer>NLHE · Integer chips · Server-validated actions · Heuristic opponents</footer>
  </main>;
}
