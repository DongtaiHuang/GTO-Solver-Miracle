import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import { handClasses, rangeMatrix } from "../lib/ranges";
import type { StudyRequest, StudyResult } from "../lib/study-types";
import { ProfileEditor } from "../components/ProfileEditor";
import { RangeMatrix } from "../components/RangeMatrix";
import { StudyDashboard } from "../components/StudyDashboard";
import { OpponentSetup, initialOpponents } from "../components/OpponentSetup";
import { profileFixtures, studyFixture } from "./study-fixtures";

function setupApi(imported?: StudyResult) {
  return vi.spyOn(api, "requestJson").mockImplementation((async (path: string, body?: unknown) => {
    if (path === "/api/profiles") return profileFixtures;
    if (path.startsWith("/api/strategy/")) return { scenarios: [], message: "No source" };
    if (path === "/api/study/current") {
      if (!imported) throw new api.ApiError("No active session; start a new hand", 404);
      return imported;
    }
    const request = body as StudyRequest;
    if (request.spot.hero_position === request.spot.opponent_position) throw new api.ApiError("Hero and opponent positions must differ", 422);
    return studyFixture(request);
  }) as typeof api.requestJson);
}

function renderRangeStudy() {
  const view = render(<StudyDashboard />);
  fireEvent.click(screen.getByRole("button", { name: "Range editing & equity" }));
  return view;
}

describe("169-class range representation", () => {
  it("contains exactly thirteen rows, pairs on the diagonal, suited above and offsuit below", () => {
    expect(rangeMatrix).toHaveLength(13);
    expect(handClasses).toHaveLength(169);
    expect(new Set(handClasses).size).toBe(169);
    expect(rangeMatrix.map((row, i) => row[i])).toEqual("AKQJT98765432".split("").map(r => r + r));
    expect(rangeMatrix[0][1]).toBe("AKs");
    expect(rangeMatrix[1][0]).toBe("AKo");
    expect(handClasses.filter(h => h.endsWith("s"))).toHaveLength(78);
    expect(handClasses.filter(h => h.endsWith("o"))).toHaveLength(78);
  });
  it("renders every hand as an accessible selectable weighted class", async () => {
    const user = userEvent.setup(), selected = vi.fn();
    render(<RangeMatrix weights={{ AA: 50 }} selected="AA" onSelect={selected} />);
    expect(within(screen.getByRole("group", { name: "169 starting hand classes" })).getAllByRole("button")).toHaveLength(169);
    expect(screen.getByRole("button", { name: "AA inclusion 50%" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "AKs inclusion 0%" }));
    expect(selected).toHaveBeenCalledWith("AKs");
  });
});

describe("editable opponent assumptions", () => {
  it("selects profiles, edits their parameters, and resets defaults", async () => {
    const user = userEvent.setup(), change = vi.fn();
    const view = render(<ProfileEditor profiles={profileFixtures} value={{ id: "tag" }} onChange={change} />);
    await user.selectOptions(screen.getByLabelText("Opponent profile"), "lp");
    expect(change).toHaveBeenLastCalledWith({ id: "lp", parameters: profileFixtures[4].parameters });
    view.rerender(<ProfileEditor profiles={profileFixtures} value={{ id: "lp", parameters: {
      ...profileFixtures[4].parameters!, vpip: 60 } }} onChange={change} />);
    expect(screen.getByLabelText("VPIP (%)")).toHaveValue(60);
    fireEvent.change(screen.getByLabelText("VPIP (%)"), { target: { value: "52" } });
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ parameters: expect.objectContaining({ vpip: 52 }) }));
    await user.click(screen.getByRole("button", { name: "Reset profile defaults" }));
    expect(change).toHaveBeenLastCalledWith({ id: "lp", parameters: profileFixtures[4].parameters });
  });
  it("never supplies fictitious Standard GTO statistics", () => {
    render(<ProfileEditor profiles={profileFixtures} value={{ id: "standard_gto" }} onChange={vi.fn()} />);
    expect(screen.getByText("Not yet solver-backed")).toBeInTheDocument();
    expect(screen.queryByLabelText("VPIP (%)")).not.toBeInTheDocument();
    expect(screen.getByText(/GTO solution unavailable/)).toBeInTheDocument();
  });
  it("configures the selected trainer seat independently", async () => {
    const user = userEvent.setup(), changed = vi.fn();
    render(<OpponentSetup profiles={profileFixtures} configs={initialOpponents()} onChange={changed} disabled={false} />);
    await user.click(screen.getByText("Opponent configuration",{exact:false,selector:"summary"}));
    await user.click(screen.getByRole("button", { name: /Seat 2/ }));
    await user.selectOptions(screen.getByLabelText("Seat 2 profile"), "tp");
    const configs = changed.mock.calls.at(-1)![0];
    expect(configs[0].id).toBe("tag");
    expect(configs[1].id).toBe("tp");
    expect(configs[2].id).toBe("tp");
  });
});

describe("study dashboard", () => {
  beforeEach(() => window.history.replaceState({}, "", "/"));
  it("shows modeled ranges and unavailable solver outputs without invented numbers", async () => {
    setupApi(); renderRangeStudy();
    await screen.findByText("Model ready");
    expect(screen.getAllByText("GTO solution unavailable").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByLabelText("Opponent profile")).toHaveValue("tag");
    expect(screen.getByText("Strategy frequencies")).toBeInTheDocument();
    expect(screen.getByText("Action EV")).toBeInTheDocument();
    expect(screen.getByText("Hand equity")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AA inclusion 100%" })).toBeInTheDocument();
  });
  it("edits hand inclusion weights and keeps hero and opponent ranges independent", async () => {
    const mock = setupApi(), user = userEvent.setup(); renderRangeStudy();
    await screen.findByText("Model ready");
    await user.click(screen.getByRole("button", { name: "Hero range" }));
    await user.click(screen.getByRole("button", { name: "KQs inclusion 0%" }));
    await user.clear(screen.getByLabelText("Selected hand inclusion weight"));
    await user.type(screen.getByLabelText("Selected hand inclusion weight"), "50");
    await waitFor(() => expect(mock).toHaveBeenLastCalledWith("/api/study", expect.objectContaining({
      hero_range: { weights: expect.objectContaining({ KQs: 50 }) }, opponent_range: null,
    }), expect.any(AbortSignal)));
    await user.click(screen.getByRole("button", { name: "Clear range" }));
    await screen.findByRole("button", { name: "KQs inclusion 0%" });
    await user.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByRole("button", { name: "72o inclusion 100%" })).toBeInTheDocument();
  });
  it("rebuilds the modeled range when selecting and editing an archetype", async () => {
    const mock = setupApi(), user = userEvent.setup(); renderRangeStudy();
    await screen.findByText("Model ready");
    await user.click(screen.getByRole("button", { name: /^LAG/ }));
    expect(screen.getByLabelText("VPIP (%)")).toHaveValue(38);
    await user.clear(screen.getByLabelText("VPIP (%)"));
    await user.type(screen.getByLabelText("VPIP (%)"), "50");
    await waitFor(() => expect(mock).toHaveBeenLastCalledWith("/api/study", expect.objectContaining({
      opponent: { id: "lag", parameters: expect.objectContaining({ vpip: 50 }) }, opponent_range: null,
    }), expect.any(AbortSignal)));
    await user.click(screen.getByRole("button", { name: "Reset profile defaults" }));
    expect(screen.getByLabelText("VPIP (%)")).toHaveValue(38);
    await user.click(screen.getByRole("button", { name: /^Standard GTO/ }));
    await screen.findByRole("button", { name: "AA inclusion 0%" });
    expect(screen.getByText("Not yet solver-backed")).toBeInTheDocument();
  });
  it("shows invalid-spot errors and recovers without displaying stale calculations", async () => {
    setupApi(); const user = userEvent.setup(); renderRangeStudy();
    await screen.findByText("Model ready");
    await user.selectOptions(screen.getByLabelText("Hero position"), "BB");
    expect(await screen.findByRole("alert")).toHaveTextContent("Hero and opponent positions must differ");
    expect(screen.queryByText("Model ready")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Hero position"), "BTN");
    await screen.findByText("Model ready");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("imports a public trainer snapshot and drops trusted legal actions after edits", async () => {
    const imported = studyFixture();
    imported.context_source = "trainer_snapshot"; imported.trainer_hand_id = "trainer-hand"; imported.trainer_revision = 4;
    imported.spot = { ...imported.spot, hero_cards: ["As", "Kd"], board: ["2c", "3c", "4h"],
      street: "flop", pot: 900, bet_sizes: [300], history: "1. preflop: Alex raise 300" };
    imported.providers.forEach(p => { p.legal_actions = ["fold", "call"]; });
    setupApi(imported); const user = userEvent.setup(); renderRangeStudy();
    await screen.findByText("Model ready");
    await user.click(screen.getByRole("button", { name: /Import trainer hand/ }));
    expect(await screen.findByText("TRAINER SNAPSHOT")).toBeInTheDocument();
    expect(screen.getByLabelText("Hero hole cards")).toHaveValue("As Kd");
    expect(screen.getByLabelText("Community cards")).toHaveValue("2c 3c 4h");
    expect(screen.getByLabelText("Pot (chips)")).toHaveValue(900);
    await user.clear(screen.getByLabelText("Pot (chips)"));
    await user.type(screen.getByLabelText("Pot (chips)"), "500");
    await screen.findByText("EDITABLE HYPOTHETICAL");
    await screen.findByText(/unavailable for manually edited spots/);
  });
  it("honors the trainer navigation link and handles a missing session", async () => {
    window.history.replaceState({}, "", "/?from=trainer");
    setupApi(); renderRangeStudy();
    expect(await screen.findByRole("alert")).toHaveTextContent("No active session");
    await screen.findByText("Model ready");
  });
});
