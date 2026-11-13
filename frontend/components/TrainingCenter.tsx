"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { requestJson } from "../lib/api";
import {
  archiveKey,
  trainingApi,
  spot,
  selectIndex,
  policyKey,
  type Prompt,
  type Archive,
  type Attempt,
  type Report,
  type Feedback,
  type Hypothesis,
} from "../lib/training";

const empty: Archive = { version: "1", attempts: [] };
async function verify(
  raw: string,
): Promise<{ archive: Archive; report: Report }> {
  if (new Blob([raw]).size > 65536)
    throw Error("Archive exceeds 64 KiB. Export and start another archive.");
  const result = await fetch(trainingApi + "report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: raw,
  });
  if (!result.ok)
    throw Error(
      "Archive failed verification. Check its version, attempt IDs and solver references.",
    );
  return await result.json();
}
export function TrainingCenter() {
  const [prompts, setPrompts] = useState<Prompt[]>([]),
    [selected, choose] = useState("");
  const [archive, setArchive] = useState<Archive>(empty),
    [report, setReport] = useState<Report>({});
  const [archiveLocked, lockArchive] = useState(false);
  const [policy, setPolicy] = useState<Hypothesis | null>(null);
  const [session, setSession] = useState(""),
    [profile, setProfile] = useState(""),
    [street, setStreet] = useState(""),
    [position, setPosition] = useState("");
  const [focus, setFocus] = useState("all"),
    [review, setReview] = useState<{ id: string; action: string } | null>(null);
  const [feedback, show] = useState<Attempt | null>(null),
    [busy, setBusy] = useState(true),
    [error, setError] = useState(""),
    [filter, setFilter] = useState("");
  async function work(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function apply(data: { archive: Archive; report: Report }) {
    sessionStorage.setItem(archiveKey, JSON.stringify(data.archive));
    setArchive(data.archive);
    setReport(data.report);
  }
  useEffect(() => {
    void work(async () => {
      const catalog = await requestJson<Prompt[]>(trainingApi + "exercises");
      setPrompts(catalog);
      const params = new URLSearchParams(location.search);
      const p = params.has("source")
        ? catalog.find(
            (x) =>
              x.solution_id === params.get("source") &&
              x.scenario_id === params.get("scenario") &&
              x.combo === params.get("combo"),
          )
        : catalog[0];
      if (params.has("policy") && p) {
        const h: Hypothesis = JSON.parse(params.get("policy")!);
        if (
          !["tag", "lag", "lp", "tp", "standard_gto"].includes(h.profile) ||
          !p.solution_id.startsWith("ts-")
        )
          throw Error("Incompatible training hypothesis");
        setPolicy(h);
        setProfile(h.profile);
      }
      choose(p ? spot(p) : "");
      if (!p) setError("Requested exercise unavailable.");
      if (p && params.get("review") && params.get("action"))
        setReview({ id: params.get("review")!, action: params.get("action")! });
      const active =
        sessionStorage.getItem("miracle.training.session") ??
        crypto.randomUUID();
      sessionStorage.setItem("miracle.training.session", active);
      setSession(active);
      const raw = sessionStorage.getItem(archiveKey);
      if (raw) {
        lockArchive(true);
        apply(await verify(raw));
        lockArchive(false);
      }
    });
  }, []);
  const p = prompts.find((x) => spot(x) === selected);
  const eligible = prompts.filter(
    (x) =>
      (!street || x.street === street) &&
      (!position || x.position === position) &&
      (!profile || x.solution_id.startsWith("ts-")),
  );
  const misses = archive.attempts
    .filter(
      (a) =>
        (a.feedback.loss_bb ?? 0) > 0 &&
        policyKey(a.submission.hypothesis) ===
          policyKey(profile ? (policy ?? { name: profile, profile }) : null),
    )
    .sort((a, b) => b.feedback.loss_bb! - a.feedback.loss_bb!);
  const pool =
    focus === "all"
      ? eligible
      : eligible.filter((x) =>
          misses.some((a) => spot(a.submission) === spot(x)),
        );
  function nextExercise() {
    if (!pool.length) return;
    if (focus === "highest") {
      const match = misses.find((a) =>
        pool.some((x) => spot(x) === spot(a.submission)),
      );
      if (match) pick(spot(match.submission));
    } else {
      const seed = crypto.getRandomValues(new Uint32Array(1))[0];
      pick(spot(pool[selectIndex(pool.length, seed)]));
    }
  }
  function pick(id: string) {
    choose(id);
    show(null);
    setReview(null);
  }
  async function save(data: Archive) {
    apply(await verify(JSON.stringify(data)));
  }
  async function submit(action: string) {
    if (!p) return;
    const submission = {
      solution_id: p.solution_id,
      scenario_id: p.scenario_id,
      combo: p.combo,
      version: p.version,
      action,
      hypothesis: profile ? (policy ?? { name: profile, profile }) : null,
    };
    const result = await requestJson<Feedback>(
      trainingApi + "grade",
      submission,
    );
    const a: Attempt = {
      submission,
      retry: archive.attempts.some(
        (x) =>
          spot(x.submission) === spot(submission) &&
          policyKey(x.submission.hypothesis) ===
            policyKey(submission.hypothesis),
      ),
      origin: review ? "review" : "practice",
      feedback: result,
      street: p.street,
      position: p.position,
      id: review?.id ?? crypto.randomUUID(),
      session,
      time: new Date().toISOString(),
    };
    if (archive.attempts.some((x) => x.id === a.id))
      throw Error("This reviewed decision is already saved.");
    await save({ ...archive, attempts: [...archive.attempts, a] });
    show(a);
  }
  const sessions = new Set(archive.attempts.map((a) => a.session));
  const graded = archive.attempts.filter(
    (a) => a.feedback.status === "graded",
  ).length;
  return (
    <main className="training-center">
      <header>
        <h1>Training Center</h1>
        <p>Practice a decision against an exact solver record.</p>
      </header>
      {error && <p role="alert">{error}</p>}
      <section aria-label="Practice statistics" className="training-stats">
        {Object.entries({
          Sessions: sessions.size,
          Decisions: archive.attempts.length,
          Graded: graded,
          Ungraded: archive.attempts.length - graded,
          "GTO loss / decision": report.GTO?.average_bb?.toFixed(4),
          "Model loss / decision": report.Model?.average_bb?.toFixed(4),
        }).map(([label, v]) => (
          <div className="study-card" key={label}>
            <small>{label}</small>
            <h2>
              {v ?? "—"} {label.includes("loss") && v !== undefined ? "BB" : ""}
            </h2>
          </div>
        ))}
      </section>
      <fieldset disabled={busy || archiveLocked} className="study-card">
        <legend>Decision practice</legend>
        <div className="training-controls">
          <label>
            Benchmark
            <select
              value={profile}
              onChange={(e) => {
                setPolicy(null);
                setProfile(e.target.value);
                pick("");
              }}
            >
              {["", "standard_gto", "tag", "lag", "tp", "lp"].map((x) => (
                <option key={x} value={x}>
                  {x ? "Model · " + x.toUpperCase() : "GTO equilibrium"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Street
            <select
              value={street}
              onChange={(e) => {
                setStreet(e.target.value);
                pick("");
              }}
            >
              {["", "turn", "river"].map((x) => (
                <option key={x} value={x}>
                  {x || "All streets"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Position
            <select
              value={position}
              onChange={(e) => {
                setPosition(e.target.value);
                pick("");
              }}
            >
              {["", "BTN", "BB"].map((x) => (
                <option key={x} value={x}>
                  {x || "Both seats"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Practice focus
            <select
              value={focus}
              onChange={(e) => {
                setFocus(e.target.value);
                pick("");
              }}
            >
              <option value="all">Random supported decisions</option>
              <option value="missed">Repeat measured losses</option>
              <option value="highest">Highest measured loss</option>
            </select>
          </label>
        </div>
        <label className="field">
          Exercise
          <select
            aria-label="Exercise"
            value={selected}
            onChange={(e) => pick(e.target.value)}
          >
            <option value="">Select an exercise</option>
            {pool.map((x) => (
              <option key={spot(x)} value={spot(x)}>
                {x.solution_id} · {x.position} · {x.combo}
              </option>
            ))}
          </select>
        </label>
        <button disabled={!pool.length} onClick={nextExercise}>
          Next exercise
        </button>
        {p && (
          <>
            <h2>
              {p.position} · {p.combo} on {p.board.join(" ")}
            </h2>
            <p>
              {p.street} · Pot {p.pot} chips · Big blind {p.blind}
            </p>
            <details>
              <summary>Public betting history and assumptions</summary>
              <p>{p.history.join(" → ")}</p>
              <p>{p.assumptions.join(" ")}</p>
            </details>
            {review ? (
              <button
                disabled={!!feedback}
                onClick={() => void work(() => submit(review.action))}
              >
                Save reviewed action {review.action}
              </button>
            ) : (
              p.actions
                .filter(
                  (a) =>
                    !(profile && a === "fold" && p.actions.includes("check")),
                )
                .map((a) => (
                  <button
                    key={a}
                    disabled={!!feedback}
                    onClick={() => void work(() => submit(a))}
                  >
                    {a}
                  </button>
                ))
            )}
            {feedback && (
              <div aria-live="polite">
                <h3>
                  {feedback.feedback.status === "ungraded"
                    ? "Ungraded"
                    : feedback.feedback.loss === 0
                      ? "Best or numerically equivalent"
                      : "Measured EV loss"}
                </h3>
                <p>
                  {feedback.feedback.reason} · Selected{" "}
                  {feedback.submission.action} ·{" "}
                  {feedback.feedback.loss?.toFixed(6) ?? "Unavailable"} chips
                </p>
                <p>
                  Best actions:{" "}
                  {feedback.feedback.best.join(", ") || "Unavailable"}
                </p>
                {Object.entries(feedback.feedback.action_ev ?? {}).map(
                  ([a, v]) => (
                    <p key={a}>
                      {a} · {v.toFixed(6)} chips · equilibrium frequency{" "}
                      {(
                        (feedback.feedback.frequencies?.[a] ?? 0) * 100
                      ).toFixed(2)}
                      %{" "}
                      {profile &&
                        " · modeled response " +
                          (
                            (feedback.feedback.response?.[a] ?? 0) * 100
                          ).toFixed(1) +
                          "%"}
                    </p>
                  ),
                )}
                {profile && (
                  <p>
                    Hypothesis {policy?.name ?? profile} ({profile}). Opening
                    rate and any row overrides apply only at their specified
                    information sets. · Conditional response gain{" "}
                    {feedback.feedback.model_gain?.toFixed(4) ?? "unavailable"}{" "}
                    · Equilibrium cost{" "}
                    {feedback.feedback.equilibrium_cost?.toFixed(4) ??
                      "unavailable"}{" "}
                    chips
                  </p>
                )}
                {profile && (
                  <details>
                    <summary>Fixed opponent policy</summary>
                    <pre>
                      {JSON.stringify(feedback.submission.hypothesis, null, 2)}
                    </pre>
                    <p>
                      All unspecified rows inherit the Task 009 reference. Model
                      gain and equilibrium cost compare policies at this
                      combination.
                    </p>
                  </details>
                )}
                <p>
                  {p.solver} · {p.accuracy}
                </p>
                <button onClick={() => pick(selected)}>Retry exercise</button>{" "}
                <Link
                  href={
                    "/?" + new URLSearchParams({source:p.solution_id, scenario:p.scenario_id, combo:p.combo})
                  }
                >
                  Inspect in Study
                </Link>
              </div>
            )}
          </>
        )}
      </fieldset>
      <section className="study-card">
        <h2>Session history</h2>
        <p>
          Tab-scoped · Up to 64 attempts or 64 KiB. Export for a durable copy.
          EV loss measures decision quality within this library, in big blinds.
        </p>
        {!graded && <p>No graded decisions yet.</p>}
        <label>
          Filter history{" "}
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Scenario, position or street"
          />
        </label>
        {archive.attempts
          .slice()
          .reverse()
          .filter((a) =>
            [a.submission.solution_id, a.position, a.street]
              .join(" ")
              .toLowerCase()
              .includes(filter.toLowerCase()),
          )
          .map((a) => (
            <details key={a.id}>
              <summary>
                {a.time.slice(0, 19)} · {a.position} {a.submission.combo} ·{" "}
                {a.submission.action} ·{" "}
                {a.feedback.loss_bb?.toFixed(4) ?? "Ungraded"} BB
              </summary>
              <p>
                {a.origin} · {a.retry ? "Retry" : "First attempt"} ·{" "}
                {a.submission.solution_id} ·{" "}
                {a.submission.hypothesis?.name ?? "GTO"} · {a.feedback.reason}
              </p>
              <button
                disabled={busy}
                onClick={() =>
                  void work(() =>
                    save({
                      ...archive,
                      attempts: archive.attempts.filter((x) => x.id !== a.id),
                    }),
                  )
                }
              >
                Delete attempt
              </button>
            </details>
          ))}
        {misses.length > 0 && (
          <aside>
            <h3>Practice recommendation</h3>
            <p>
              Largest measured loss for this benchmark:{" "}
              {misses[0].submission.solution_id}, {misses[0].submission.combo} (
              {misses[0].feedback.loss_bb?.toFixed(4)} BB).
            </p>
            <button
              onClick={() => {
                const a = misses[0];
                setStreet("");
                setPosition("");
                setFocus("all");
                setProfile(a.submission.hypothesis?.profile ?? "");
                setPolicy(a.submission.hypothesis);
                pick(spot(a.submission));
              }}
            >
              Revisit this decision
            </button>
          </aside>
        )}
        <details>
          <summary>Session trends and recurring losses</summary>
          {["GTO", "Model"].map((mode) => {
            const rows = Object.entries(report).filter(
              ([k, v]) =>
                k.startsWith(mode + " · session ") && v.average_bb !== null,
            );
            const peak = Math.max(
              0.000001,
              ...rows.map(([, v]) => v.average_bb!),
            );
            return (
              <section key={mode}>
                <h3>{mode} · mean loss per recorded session</h3>
                {rows.length ? (
                  rows.map(([key, v]) => (
                    <p key={key}>
                      {key.split("session ")[1].slice(0, 8)}{" "}
                      <meter min={0} max={peak} value={v.average_bb!} />{" "}
                      {v.average_bb!.toFixed(4)} BB
                    </p>
                  ))
                ) : (
                  <p>No graded sessions.</p>
                )}
              </section>
            );
          })}
          {Object.entries(report)
            .filter(([k, v]) => k.includes(" · weakness ") && v.count > 1)
            .map(([k, v]) => (
              <p key={k}>
                {k} · {v.count} measured losses, including retries
              </p>
            ))}
        </details>
        <details>
          <summary>
            Performance by session, street, position and scenario
          </summary>
          {Object.entries(report).map(([key, m]) => (
            <p key={key}>
              {key} · {m.graded}/{m.count} graded · mean{" "}
              {m.average_bb?.toFixed(4) ?? "unavailable"} BB · total{" "}
              {m.total_bb?.toFixed(4) ?? "unavailable"} BB
            </p>
          ))}
        </details>
        <button
          onClick={() => {
            const id = crypto.randomUUID();
            setSession(id);
            sessionStorage.setItem("miracle.training.session", id);
            pick("");
          }}
        >
          Begin new session
        </button>
        <button
          onClick={() => {
            const url = URL.createObjectURL(
              new Blob(
                [sessionStorage.getItem(archiveKey) ?? JSON.stringify(archive)],
                { type: "application/json" },
              ),
            );
            const a = document.createElement("a");
            a.href = url;
            a.download = "miracle-training.json";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }}
        >
          Export history
        </button>
        <label>
          Replace from JSON{" "}
          <input
            disabled={busy}
            type="file"
            accept=".json"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file)
                void work(async () => {
                  if (file.size > 65536) throw Error("Archive exceeds 64 KiB");
                  apply(await verify(await file.text()));
                  lockArchive(false);
                  show(null);
                });
            }}
          />
        </label>
        <button
          disabled={busy}
          onClick={() => {
            if (confirm("Delete training history in this tab?"))
              void work(async () => {
                await save(empty);
                lockArchive(false);
                show(null);
              });
          }}
        >
          Reset history
        </button>
      </section>
    </main>
  );
}
