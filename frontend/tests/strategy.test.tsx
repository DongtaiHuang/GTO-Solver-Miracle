import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { StrategyResult, StrategyScenarioIndex } from "../lib/strategy-types";
import { StrategyMatrix, FrequencyChart } from "../components/StrategyMatrix";
import { StrategyWorkspace } from "../components/StrategyWorkspace";
import { StrategyComparison } from "../components/StrategyComparison";
import { StudyDashboard } from "../components/StudyDashboard";
import { profileFixtures } from "./study-fixtures";
import fixture from "./strategy-fixture.json";

// Actual synthetic provider output. No solver source is claimed or installed by these tests.
const sample = fixture as unknown as StrategyResult;
const demoIndex: StrategyScenarioIndex = {
  scenarios: [{ solution_id: sample.source!.solution_id, scenario_id: sample.scenario_id,
    kind: "synthetic_fixture", scenario: sample.scenario, label: "Synthetic preflop test" }],
  message: "Synthetic UI only",
};
function mockApi(query?: () => Promise<StrategyResult>) {
  return vi.spyOn(api, "requestJson").mockImplementation((async (path: string) => {
    if (path === "/api/profiles") return profileFixtures;
    if (path === "/api/strategy/scenarios") return { scenarios: [], message: "GTO solution unavailable" };
    if (path === "/api/strategy/examples") return demoIndex;
    if (path === "/api/strategy/query") return query ? query() : sample;
    throw new Error("Unexpected request: " + path);
  }) as typeof api.requestJson);
}
function workspace() {
  return render(<StrategyWorkspace profiles={profileFixtures} opponent={{ id: "tag" }} onOpponentChange={vi.fn()} />);
}
async function chooseDemo() {
  fireEvent.click(screen.getByRole("checkbox", { name: /Show synthetic examples/ }));
  await screen.findByRole("option", { name: "Synthetic preflop test" });
  fireEvent.change(screen.getByLabelText("Supported exact scenario"), {
    target: { value: sample.source!.solution_id },
  });
}

describe("mixed strategy matrix and probabilities", () => {
  it("renders 169 selectable classes with proportional, sized action segments", () => {
    const selected = vi.fn();
    render(<StrategyMatrix classes={sample.classes} actions={sample.actions} selected="AA" onSelect={selected} demo />);
    const matrix = screen.getByRole("group", { name: "Synthetic strategy matrix" });
    expect(within(matrix).getAllByRole("button")).toHaveLength(169);
    const aa = screen.getByRole("button", { name: "AA strategy coverage 2/6" });
    expect(aa).toHaveAttribute("aria-pressed", "true");
    expect(aa.querySelectorAll("i")).toHaveLength(5);
    expect(parseFloat((aa.querySelectorAll("i")[sample.actions.findIndex(a => a.key === "fold")] as HTMLElement).style.width)).toBeCloseTo(13.333, 2);
    const missing = screen.getByRole("button", { name: "72o strategy unavailable" });
    expect(missing.querySelectorAll("i")).toHaveLength(0);
    fireEvent.click(missing); expect(selected).toHaveBeenCalledWith("72o");
  });
  it("shows exact action sizes and no invented frequencies when unavailable", () => {
    const view = render(<FrequencyChart frequencies={null} actions={sample.actions} label="Test distribution" />);
    expect(screen.getByText("GTO solution unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    view.rerender(<FrequencyChart frequencies={sample.frequencies} actions={sample.actions} label="Test distribution" />);
    expect(screen.getByText("raise to 200")).toBeInTheDocument();
    expect(screen.getByText("raise to 300")).toBeInTheDocument();
    expect(screen.getByText("call 100")).toBeInTheDocument();
  });
});

describe("exact scenario workspace", () => {
  it("makes strategy the default without requesting or displaying synthetic recommendations", async () => {
    const mock = mockApi();
    render(<StudyDashboard />);
    await screen.findByText(/0 public approved scenarios/);
    expect(screen.getByRole("group", { name: "GTO strategy matrix" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(mock.mock.calls.some(([path]) => path === "/api/strategy/query")).toBe(false);
    expect(screen.queryByText("13.3%")).not.toBeInTheDocument();
  });
  it("requires explicit demo mode, exposes combo distributions and clears on switching back", async () => {
    const mock = mockApi(); workspace(); await chooseDemo();
    fireEvent.click(screen.getByRole("button", { name: "Query exact strategy" }));
    await screen.findByRole("status", { name: "Strategy coverage status" });
    expect(mock).toHaveBeenCalledWith("/api/strategy/query",
      { scenario: sample.scenario, mode: "synthetic_demo" }, expect.any(AbortSignal));
    expect(screen.getByText("SYNTHETIC DEMONSTRATION — NOT GTO")).toBeInTheDocument();
    const detail = screen.getByRole("region", { name: "Selected hand strategy" });
    expect(within(detail).getByText("13.3%")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Inspect combination"), { target: { value: "AcAd" } });
    expect(within(detail).getByText("10.0%")).toBeInTheDocument();
    expect(within(detail).queryByText("13.3%")).not.toBeInTheDocument();
    expect(screen.getByText(/Validated action EV unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Solution provenance" })).toHaveTextContent("synthetic_only");
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.queryByRole("status", { name: "Strategy coverage status" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AA strategy unavailable" })).toBeInTheDocument();
  });
  it("reports unsupported states without substituting a nearby solution", async () => {
    mockApi(async () => ({ ...sample, status: "unavailable", source: null, combinations: [], classes: [],
      frequencies: null, action_ev: null, represented_combos: 0, message: "GTO solution unavailable" }));
    workspace(); await chooseDemo();
    fireEvent.click(screen.getByRole("button", { name: "Query exact strategy" }));
    const status = await screen.findByRole("status", { name: "Strategy coverage status" });
    expect(status).toHaveTextContent("GTO solution unavailable");
    expect(screen.getByRole("button", { name: "AA strategy unavailable" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Inspect combination")).not.toBeInTheDocument();
  });
  it("validates JSON and handles server failures without rendering arbitrary input", async () => {
    const mock = mockApi(async () => { throw new api.ApiError("Scenario conflicts with engine", 422); });
    workspace(); await screen.findByText(/0 public approved scenarios/);
    const editor = screen.getByLabelText("Exact scenario JSON");
    fireEvent.change(editor, { target: { value: "invalid-json" } });
    fireEvent.click(screen.getByRole("button", { name: "Query exact strategy" }));
    await screen.findByRole("alert");
    expect(mock.mock.calls.some(([path]) => path === "/api/strategy/query")).toBe(false);
    fireEvent.change(editor, { target: { value: '{"board":[{}],"game_format":{}}' } });
    fireEvent.click(screen.getByRole("button", { name: "Query exact strategy" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Scenario conflicts with engine");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
  it("ignores stale results after the scenario changes", async () => {
    let resolve!: (value: StrategyResult) => void;
    const pending = new Promise<StrategyResult>(done => { resolve = done; });
    mockApi(() => pending); workspace(); await chooseDemo();
    fireEvent.click(screen.getByRole("button", { name: "Query exact strategy" }));
    fireEvent.change(screen.getByLabelText("Exact scenario JSON"), { target: { value: "{}" } });
    resolve(sample);
    await waitFor(() => expect(screen.getByRole("button", { name: "Query exact strategy" })).toBeEnabled());
    expect(screen.queryByRole("status", { name: "Strategy coverage status" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AA strategy unavailable" })).toBeInTheDocument();
  });
  it("shows catalog errors without filling strategy cells", async () => {
    vi.spyOn(api, "requestJson").mockRejectedValue(new Error("Catalog offline"));
    workspace();
    expect(await screen.findByRole("alert")).toHaveTextContent("Catalog offline");
    expect(screen.getByRole("button", { name: "AA strategy unavailable" })).toBeInTheDocument();
  });
});

describe("baseline versus opponent assumptions", () => {
  it("keeps synthetic probabilities separate from all five modeled profiles and edits", () => {
    const onChange = vi.fn();
    const view = render(<StrategyComparison result={sample} profiles={profileFixtures} opponent={{ id: "tag" }} onChange={onChange} />);
    expect(screen.getByText("SYNTHETIC DEMO ONLY")).toBeInTheDocument();
    expect(screen.getByText(/No exploitative best response/)).toBeInTheDocument();
    expect(screen.getByText("24%")).toBeInTheDocument();
    const baseline = screen.getByLabelText("Synthetic baseline demonstration").textContent;
    for (const profile of profileFixtures) {
      view.rerender(<StrategyComparison result={sample} profiles={profileFixtures} opponent={{ id: profile.id }} onChange={onChange} />);
      expect(screen.getByLabelText("Synthetic baseline demonstration").textContent).toBe(baseline);
      if (profile.id === "standard_gto") {
        expect(screen.getByText(/No statistical parameters or opponent action frequencies are invented/)).toBeInTheDocument();
        expect(screen.queryByText("24%")).not.toBeInTheDocument();
      } else expect(screen.getByText(profile.parameters!.vpip + "%")).toBeInTheDocument();
    }
    fireEvent.change(screen.getByLabelText("VPIP (%)"), { target: { value: "60" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      parameters: expect.objectContaining({ vpip: 60 }),
    }));
    expect(screen.getByLabelText("Synthetic baseline demonstration").textContent).toBe(baseline);
  });
  it("displays the reviewed-source contract separately from unavailable output", () => {
    // A test-only response contract, not a real dataset or recommendation.
    const view = render(<StrategyComparison result={{ ...sample, status: "available" }}
      profiles={profileFixtures} opponent={{ id: "tag" }} onChange={vi.fn()} />);
    expect(screen.getByText("REVIEWED SOLVER DATA")).toBeInTheDocument();
    view.rerender(<StrategyComparison result={null} profiles={profileFixtures} opponent={{ id: "tag" }} onChange={vi.fn()} />);
    expect(screen.getByText("GTO solution unavailable")).toBeInTheDocument();
    expect(screen.queryByText("REVIEWED SOLVER DATA")).not.toBeInTheDocument();
  });
});
