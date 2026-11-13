"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { requestJson, ApiError } from "../../lib/api";
import {
  persist,
  readArchive,
  type Archive as Observations,
} from "../../lib/observations";
import { archiveKey, type Archive as Training } from "../../lib/training";
import type { Hand } from "../../lib/analyzer";

const api = "/api/account/";
type Saved = { id: string; title: string };
type Snapshot = { archive: Observations; revision: number };
interface Google {
  accounts: {
    id: {
      initialize: (o: {
        client_id: string;
        nonce: string;
        callback: (r: { credential: string }) => void;
      }) => void;
      renderButton: (
        el: HTMLElement,
        o: { theme: string; size: string },
      ) => void;
    };
  };
}
declare global {
  interface Window {
    google?: Google;
  }
}
function download(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name + ".json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function Account() {
  const [name, who] = useState(""),
    [busy, wait] = useState(true),
    [message, notice] = useState(""),
    [error, fail] = useState("");
  const [hands, setHands] = useState<Saved[]>([]),
    [sessions, setSessions] = useState<string[]>([]),
    [revision, setRevision] = useState(0);
  const [locals, setLocals] = useState<string[]>([]),
    [hasObs, foundObs] = useState(false),
    [hasTraining, foundTraining] = useState(false);
  const [active, open] = useState<Training | null>(null),
    [page, setPage] = useState(0);
  const sign = useRef<HTMLDivElement>(null);
  async function run(fn: () => Promise<void>) {
    wait(true);
    fail("");
    notice("");
    try {
      await fn();
    } catch (e) {
      if(e instanceof ApiError && e.status===401){
        who(""); setHands([]); setSessions([]); open(null); setRevision(0); setPage(0);
      }
      fail(String(e));
    } finally {
      wait(false);
    }
  }
  async function refresh(offset = page) {
    const [h, s, o] = await Promise.all([
      requestJson<Saved[]>(api + "hands?offset=" + offset),
      requestJson<string[]>(api + "sessions?offset=" + offset),
      requestJson<Snapshot>(api + "observations"),
    ]);
    setHands(h);
    setSessions(s);
    if (offset === 0 && !name) setRevision(o.revision);
    setPage(offset);
  }
  useEffect(() => {
    void run(async () => {
      setLocals(
        Object.keys(sessionStorage).filter((k) =>
          k.startsWith("miracle.analyzer.v1."),
        ),
      );
      foundObs(!!sessionStorage.getItem("miracle.observations.v1"));
      foundTraining(!!sessionStorage.getItem(archiveKey));
      try {
        const u = await requestJson<{ name: string }>(api + "me");
        who(u.name);
        await refresh(0);
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 401) throw e;
      }
    });
  }, []);
  useEffect(()=>{
    const changed=()=>location.reload();
    const restore=(event:PageTransitionEvent)=>{if(event.persisted)changed();};
    const onStorage=(event:StorageEvent)=>{if(event.key==="miracle.account.changed")changed();};
    window.addEventListener("storage",onStorage);
    window.addEventListener("pageshow",restore);
    return ()=>{window.removeEventListener("storage",onStorage);window.removeEventListener("pageshow",restore);};
  },[]);
  function identityChanged(){
    try {localStorage.setItem("miracle.account.changed",crypto.randomUUID());}finally{location.reload();}
  }
  async function signin() {
    const c = await requestJson<{ client_id: string; nonce: string }>(
      api + "challenge",
      {},
    );
    if (!window.google) {
      await new Promise<void>((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://accounts.google.com/gsi/client";
        s.onload = () => resolve();
        s.onerror = () => reject(Error("Identity provider unavailable"));
        document.head.appendChild(s);
      });
    }
    window.google!.accounts.id.initialize({
      ...c,
      callback: (r) =>
        void run(async () => {
          await requestJson(
            api + "login",
            r.credential ? { credential: r.credential } : {},
          );
          identityChanged();
        }),
    });
    if (sign.current) {
      sign.current.replaceChildren();
      window.google!.accounts.id.renderButton(sign.current, {
        theme: "outline",
        size: "large",
      });
    }
  }
  async function saved(id: string) {
    return requestJson<Saved & { hand: Hand }>(api + "hands/" + id);
  }
  async function loadSession(id: string) {
    const full: Training = { version: "1", attempts: [] };
    for (let offset = 0; ; offset += 64) {
      const part = await requestJson<Training>(
        api + "sessions/" + id + "?offset=" + offset,
      );
      full.attempts.push(...part.attempts);
      if (part.attempts.length < 64) break;
    }
    open(full);
  }
  async function continueSession() {
    if (!active) return;
    if (
      !confirm(
        "Replace training history in this tab and continue this session? Export local progress first.",
      )
    )
      return;
    const verified = await requestJson<{ archive: Training }>(
      "/api/strategy/training/report",
      active,
    );
    const json = JSON.stringify(verified.archive);
    if (new Blob([json]).size > 65536)
      throw Error("Session exceeds the tab history limit. Export it instead.");
    sessionStorage.setItem(archiveKey, json);
    if (active.attempts[0])
      sessionStorage.setItem(
        "miracle.training.session",
        active.attempts[0].session,
      );
    location.assign("/training");
  }
  return (
    <main className="study-page">
      <h1>Player account</h1>
      <section className="study-card" aria-busy={busy}>
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        {!name ? (
          <>
            <h2>Guest workspace</h2>
            <p>
              Study, Trainer and Training Center are available to guests. Sign
              in to save private records across devices.
            </p>
            <button disabled={busy} onClick={() => void run(signin)}>
              Sign in with Google
            </button>
            <div ref={sign} />
          </>
        ) : (
          <fieldset disabled={busy}>
            <legend>{name}</legend>
            <button
              onClick={() =>
                void run(async () => {
                  await requestJson(api + "logout", {});
                  identityChanged();
                })
              }
            >
              Sign out
            </button>
            <p>
              Tab data is imported explicitly. Importing keeps the original tab
              copy.
            </p>
            <h2>Saved hands</h2>
            {hands.map((h) => (
              <p key={h.id}>
                {h.title} ·{" "}
                <Link href={"/analyzer?saved=" + h.id}>Open in Analyzer</Link>{" "}
                <button
                  onClick={() =>
                    void run(async () =>
                      download(h.title, (await saved(h.id)).hand),
                    )
                  }
                >
                  Export
                </button>
                <button
                  onClick={() =>
                    void run(async () => {
                      if (confirm("Delete this saved hand?")) {
                        await requestJson(
                          api + "hands/" + h.id + "/delete",
                          {},
                        );
                        await refresh();
                      }
                    })
                  }
                >
                  Delete hand
                </button>
              </p>
            ))}
            {locals.map((k) => (
              <button
                key={k}
                onClick={() =>
                  void run(async () => {
                    await requestJson(api + "hands", {
                      title: k.slice("miracle.analyzer.v1.".length),
                      hand: JSON.parse(sessionStorage.getItem(k)!),
                    });
                    await refresh();
                    notice("Hand saved.");
                  })
                }
              >
                Import {k.slice("miracle.analyzer.v1.".length)}
              </button>
            ))}
            <h2>Opponent observations</h2>
            <p>
              Last loaded server revision {revision}. Replace requires that
              revision to match.
            </p>
            <button
              disabled={!hasObs}
              onClick={() =>
                void run(async () => {
                  if (
                    confirm(
                      "Replace the server archive with this tab’s validated evidence?",
                    )
                  ) {
                    const r = await requestJson<{ revision: number }>(
                      api + "observations",
                      { revision, archive: readArchive() },
                    );
                    setRevision(r.revision);
                    notice("Archive saved.");
                  }
                })
              }
            >
              Replace server observations
            </button>
            <button
              onClick={() =>
                void run(async () => {
                  const r = await requestJson<Snapshot>(api + "observations");
                  if (
                    confirm(
                      "Replace observations in this tab with the loaded server archive?",
                    )
                  ) {
                    persist(r.archive);
                    setRevision(r.revision);
                    foundObs(true);
                    notice("Server archive loaded into this tab.");
                  }
                })
              }
            >
              Load observations
            </button>
            <button
              onClick={() =>
                void run(async () =>
                  download(
                    "observations",
                    (await requestJson<Snapshot>(api + "observations")).archive,
                  ),
                )
              }
            >
              Export server evidence
            </button>
            <h2>Training history</h2>
            <button
              disabled={!hasTraining}
              onClick={() =>
                void run(async () => {
                  const r = await requestJson<{
                    added: number;
                    duplicates: number;
                  }>(
                    api + "training",
                    JSON.parse(sessionStorage.getItem(archiveKey)!),
                  );
                  await refresh();
                  notice(
                    r.added +
                      " attempts saved, " +
                      r.duplicates +
                      " duplicates.",
                  );
                })
              }
            >
              Merge tab attempts
            </button>
            {sessions.map((s) => (
              <p key={s}>
                <button onClick={() => void run(() => loadSession(s))}>
                  Review session {s.slice(0, 8)}
                </button>{" "}
                <button
                  onClick={() =>
                    void run(async () => {
                      if (confirm("Delete this training session?")) {
                        await requestJson(
                          api + "sessions/" + s + "/delete",
                          {},
                        );
                        open(null);
                        await refresh();
                      }
                    })
                  }
                >
                  Delete session
                </button>
              </p>
            ))}
            {active && (
              <div>
                {active.attempts.map((a) => (
                  <p key={a.id}>
                    {a.time} · {a.submission.solution_id} · {a.submission.combo}{" "}
                    · {a.submission.hypothesis?.name ?? "GTO"} ·{" "}
                    {a.submission.action} · {a.feedback.loss ?? "Ungraded"}{" "}
                    chips{" "}
                    <button
                      onClick={() =>
                        void run(async () => {
                          if (confirm("Delete this attempt?")) {
                            await requestJson(
                              api + "attempts/" + a.id + "/delete",
                              {},
                            );
                            await loadSession(a.session);
                          }
                        })
                      }
                    >
                      Delete attempt
                    </button>
                  </p>
                ))}
                <button onClick={() => download("training-session", active)}>
                  Export session
                </button>
                <button
                  disabled={
                    !active.attempts.length || active.attempts.length > 64
                  }
                  onClick={() => void run(continueSession)}
                >
                  Continue in Training Center
                </button>
              </div>
            )}
            <button
              disabled={!page}
              onClick={() => void run(() => refresh(page - 50))}
            >
              Previous page
            </button>
            <button
              disabled={hands.length < 50 && sessions.length < 50}
              onClick={() => void run(() => refresh(page + 50))}
            >
              Next page
            </button>
            <details>
              <summary>Delete personal data</summary>
              <button
                onClick={() =>
                  void run(async () => {
                    if (
                      confirm("Permanently clear all saved training sessions?")
                    ) {
                      await requestJson(api + "training/clear", {
                        confirm: true,
                      });
                      open(null);
                      await refresh(0);
                    }
                  })
                }
              >
                Clear saved training
              </button>
              <button
                onClick={() =>
                  void run(async () => {
                    if (
                      confirm(
                        "Permanently delete this account and all server records?",
                      )
                    ) {
                      await requestJson(api + "delete", { confirm: true });
                      identityChanged();
                    }
                  })
                }
              >
                Delete account
              </button>
            </details>
          </fieldset>
        )}
      </section>
    </main>
  );
}
