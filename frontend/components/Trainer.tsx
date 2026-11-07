"use client";
import { useCallback, useEffect, useState } from "react";
import { ApiError, requestGame } from "../lib/api";
import type { Action, GameState } from "../lib/types";
import { ActionControls } from "./ActionControls";
import { HistoryPanel } from "./HistoryPanel";
import { PokerTable } from "./PokerTable";
import { ShowdownResult } from "./ShowdownResult";
import { chips } from "./PlayerSeat";
export function Trainer() {
  const [game, setGame] = useState<GameState | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [needsSync, setNeedsSync] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      setGame(await requestGame("/api/game")); setNeedsSync(false); setError("");
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
  return <main className="trainer">
    <header className="app-header"><div><p className="eyebrow">POKER STRATEGY LAB</p><h1>Play the hand.</h1></div>
      <div className="header-actions"><span className="practice-badge">Practice / 6-max</span>
        <button className="primary" disabled={busy || needsSync || (!!game && !completed)}
          onClick={() => void mutate("/api/games", {})}>New Hand</button></div></header>
    <p className="subtitle">Read the table. Make your decision. Five heuristic opponents — no GTO claims.</p>
    {error && <div className="error-banner" role="alert">{error}
      <button disabled={busy} onClick={() => void refresh()}>Refresh table</button></div>}
    {game ? <>
      <div className="game-metrics"><span>Hand <b>#{game.hand_number}</b></span><span>Blinds <b>50 / 100</b></span>
        <span>Hero effective <b>{chips(game.effective_stack)} chips</b></span>
        <span aria-live="polite">{busy ? "Processing…" : completed ? "Hand complete" : "Your turn"}</span></div>
      <div className="workspace"><div className="play-area">
        <PokerTable game={game} />
        {completed ? <ShowdownResult game={game} /> :
          <ActionControls key={`${game.hand_id}-${game.revision}`} legal={game.legal}
            disabled={busy || needsSync || game.actor !== game.hero} onAction={act} />}
      </div><HistoryPanel entries={game.history} /></div>
      {completed && <p className="session-note">Start a new hand to reset all stacks to 100 BB and rotate the button.</p>}
    </> : <section className="welcome"><div className="welcome-mark">♠</div><h2>{busy ? "Loading your table…" : "Your seat is ready."}</h2>
      <p>Six seats. 100 big blinds. Every decision is yours.</p>
      <p>Choose New Hand to begin. Cards and chip accounting stay on the server.</p></section>}
    <footer>NLHE · Integer chips · Server-validated actions · Heuristic opponents</footer>
  </main>;
}
