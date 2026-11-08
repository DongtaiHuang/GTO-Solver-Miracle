import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { EquityResult } from "../lib/equity-types";
import type { StudyRequest } from "../lib/study-types";
import { EquityAnalysis } from "../components/EquityAnalysis";
import { studyFixture } from "./study-fixtures";

function request(): StudyRequest {
  return { spot: { ...studyFixture().spot, hero_cards: ["As", "Ah"],
      board: ["2c", "3d", "7h", "8c", "Jd"], street: "river", pot: 300 },
    opponent: { id: "tag" }, hero_range: { weights: { AA: 100 } },
    opponent_range: { weights: { KK: 100 } } };
}
function equity(sampled = false): EquityResult {
  return { method: sampled ? "monte_carlo" : "exact",
    players: [{ win_probability: sampled ? 0.4 : 1, tie_probability: 0,
      loss_probability: sampled ? 0.6 : 0, equity: sampled ? 0.4 : 1,
      uncertainty: sampled ? { standard_error: 0.01, lower: 0.3, upper: 0.5,
        confidence_level: 0.95, interval_method: "hoeffding_95_simultaneous" } : null },
      { win_probability: 0, tie_probability: 0, loss_probability: 1, equity: 0, uncertainty: null }],
    evaluated_outcomes: sampled ? 2000 : 6, valid_samples: sampled ? 2000 : null,
    proposals: sampled ? 2000 : 0, seed: sampled ? 42 : null,
    unblocked_combinations: [1, 6], work_upper_bound: "6",
    distribution: "Product weights conditioned on disjoint cards", assumptions: ["Test fixture"] };
}
function mockResult(result = equity()) {
  return vi.spyOn(api, "requestJson").mockResolvedValue(result);
}
function show(req = request()) {
  return render(<EquityAnalysis request={req} study={studyFixture(req)} onAdoptRange={vi.fn()} />);
}

describe("real equity controls", () => {
  it("calculates only on demand using the selected hands, range, board and seed", async () => {
    const mock = mockResult(), user = userEvent.setup(); show();
    expect(mock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(mock).toHaveBeenCalledWith("/api/equity/hand-vs-range", {
      hero_cards: ["As", "Ah"], opponent_range: { weights: { KK: 100 } },
      board: request().spot.board, dead: [], method: "auto", samples: 2000, seed: 42,
    }, expect.any(AbortSignal));
    const result = await screen.findByLabelText("Equity results");
    expect(result).toHaveTextContent("Total equity");
    expect(result).toHaveTextContent("100.00%");
    expect(result).toHaveTextContent("Exact enumeration");
    expect(result).toHaveTextContent("no sampling uncertainty");
  });
  it("requires explicit adoption rather than deriving equity from profile statistics", async () => {
    const user = userEvent.setup(), adopted = vi.fn(), req = { ...request(), opponent_range: null };
    const view = render(<EquityAnalysis request={req} study={studyFixture(req)} onAdoptRange={adopted} />);
    expect(screen.getByRole("button", { name: "Calculate equity" })).toBeDisabled();
    expect(screen.getByText(/No calibrated range/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use displayed range as assumption" }));
    expect(adopted).toHaveBeenCalledWith(studyFixture(req).opponent_range.weights);
    view.rerender(<EquityAnalysis request={request()} study={studyFixture()} onAdoptRange={adopted} />);
    expect(screen.getByRole("button", { name: "Calculate equity" })).toBeEnabled();
    const gto = { ...req, opponent: { id: "standard_gto" as const } };
    view.rerender(<EquityAnalysis request={gto} study={studyFixture(gto)} onAdoptRange={adopted} />);
    expect(screen.getByRole("button", { name: "Use displayed range as assumption" })).toBeDisabled();
  });
  it("supports hand-vs-hand, range-vs-range and range-vs-hand", async () => {
    const mock = mockResult(), user = userEvent.setup(); show();
    await user.selectOptions(screen.getByLabelText("Opponent equity input"), "hand");
    await user.type(screen.getByLabelText("Opponent hole cards"), "Ks Kh");
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(mock).toHaveBeenLastCalledWith("/api/equity/hand-vs-hand", expect.objectContaining({
      opponent_cards: ["Ks", "Kh"], hero_cards: ["As", "Ah"],
    }), expect.any(AbortSignal));
    await screen.findByLabelText("Equity results");
    await user.selectOptions(screen.getByLabelText("Hero equity input"), "range");
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(mock).toHaveBeenLastCalledWith("/api/equity/multiway", expect.objectContaining({
      players: [{ range: { weights: { AA: 100 } } }, { cards: ["Ks", "Kh"] }],
    }), expect.any(AbortSignal));
    await screen.findByLabelText("Equity results");
    await user.selectOptions(screen.getByLabelText("Opponent equity input"), "range");
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(mock).toHaveBeenLastCalledWith("/api/equity/range-vs-range", expect.objectContaining({
      hero_range: { weights: { AA: 100 } }, opponent_range: { weights: { KK: 100 } },
    }), expect.any(AbortSignal));
  });
  it("shows MC sample counts, confidence intervals, seed and standard error", async () => {
    mockResult(equity(true)); const user = userEvent.setup(); show();
    await user.selectOptions(screen.getByLabelText("Calculation method"), "monte_carlo");
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    const result = await screen.findByLabelText("Equity results");
    expect(result).toHaveTextContent("Monte Carlo estimate");
    expect(result).toHaveTextContent("2,000 valid samples · seed 42");
    expect(result).toHaveTextContent("30.00%–50.00%");
    expect(result).toHaveTextContent("Standard error: 1.00%");
  });
  it("keeps work requests bounded and requires a nonempty hero range", async () => {
    const mock = mockResult(), user = userEvent.setup(), req = request();
    const view = show(req);
    await user.clear(screen.getByLabelText("Simulations"));
    await user.type(screen.getByLabelText("Simulations"), "10001");
    expect(screen.getByRole("button", { name: "Calculate equity" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Simulations"));
    await user.type(screen.getByLabelText("Simulations"), "100");
    await user.clear(screen.getByLabelText("Random seed"));
    await user.type(screen.getByLabelText("Random seed"), "1.5");
    expect(screen.getByRole("button", { name: "Calculate equity" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Random seed"));
    await user.type(screen.getByLabelText("Random seed"), "1");
    await user.selectOptions(screen.getByLabelText("Hero equity input"), "range");
    view.rerender(<EquityAnalysis request={{ ...req, hero_range: { weights: {} } }} study={studyFixture()} onAdoptRange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Calculate equity" })).toBeDisabled();
    expect(mock).not.toHaveBeenCalled();
  });
  it("reports empty-range/work-limit errors and allows a corrected request", async () => {
    const mock = vi.spyOn(api, "requestJson").mockRejectedValueOnce(new api.ApiError("Range is empty after blockers", 400))
      .mockResolvedValueOnce(equity());
    const user = userEvent.setup(); show();
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Range is empty after blockers");
    await user.type(screen.getByLabelText("Dead cards"), "Ts");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    await screen.findByLabelText("Equity results");
    expect(mock).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({ dead: ["Ts"] }), expect.any(AbortSignal));
  });
  it("discards late responses when cards change and never auto-restarts expensive work", async () => {
    let resolve!: (data: EquityResult) => void;
    const pending = new Promise<EquityResult>(r => { resolve = r; });
    const mock = vi.spyOn(api, "requestJson").mockReturnValueOnce(pending);
    const user = userEvent.setup(), req = request(), view = show(req);
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    expect(screen.getByRole("button", { name: "Calculating equity…" })).toBeDisabled();
    view.rerender(<EquityAnalysis request={{ ...req, spot: { ...req.spot, board: ["2c", "3d", "7h"] } }} study={null} onAdoptRange={vi.fn()} />);
    await act(async () => resolve(equity()));
    expect(screen.queryByLabelText("Equity results")).not.toBeInTheDocument();
    expect(mock).toHaveBeenCalledTimes(1);
  });
});

describe("pot odds and simplified call EV", () => {
  it("uses calculated equity and sampling bounds, while keeping pot edits separate from equity", async () => {
    const mock = vi.spyOn(api, "requestJson").mockResolvedValueOnce(equity(true))
      .mockResolvedValueOnce({ required_equity: 0.25, call_ev: 60, call_ev_interval: [20,100],
        explanation: "No future betting, no rake, no separate side pots." });
    const user = userEvent.setup(), req = request(), view = show(req);
    expect(screen.getByRole("button", { name: "Calculate pot odds" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    await screen.findByLabelText("Equity results");
    await user.clear(screen.getByLabelText("Hero call amount (chips)"));
    await user.type(screen.getByLabelText("Hero call amount (chips)"), "100");
    await user.click(screen.getByRole("button", { name: "Calculate pot odds" }));
    expect(mock).toHaveBeenLastCalledWith("/api/equity/pot-odds", { pot: 300, call: 100, equity: 0.4,
      equity_interval: [0.3, 0.5] }, expect.any(AbortSignal));
    const odds = await screen.findByLabelText("Pot odds results");
    expect(odds).toHaveTextContent("25.00%");
    expect(odds).toHaveTextContent("60.00 chips");
    view.rerender(<EquityAnalysis request={{ ...req, spot: { ...req.spot, pot: 400 } }} study={studyFixture()} onAdoptRange={vi.fn()} />);
    await waitFor(() => expect(screen.queryByLabelText("Pot odds results")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Equity results")).toBeInTheDocument();
    expect(mock).toHaveBeenCalledTimes(2);
  });
  it("handles pot-odds server errors without losing the equity result", async () => {
    vi.spyOn(api, "requestJson").mockResolvedValueOnce(equity()).mockRejectedValueOnce(new api.ApiError("Invalid pot input", 400));
    const user = userEvent.setup(); show();
    await user.click(screen.getByRole("button", { name: "Calculate equity" }));
    await screen.findByLabelText("Equity results");
    await user.click(screen.getByRole("button", { name: "Calculate pot odds" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid pot input");
    expect(screen.getByLabelText("Equity results")).toBeInTheDocument();
  });
});
