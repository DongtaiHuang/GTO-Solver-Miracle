import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActionControls } from "../components/ActionControls";
import { PokerTable } from "../components/PokerTable";
import { gameState, completedState } from "./fixtures";
describe("engine supplied action controls", () => {
  it("uses server presets and submits raise-to integer chips", async () => {
    const onAction = vi.fn(), user = userEvent.setup();
    render(<ActionControls legal={gameState().legal} disabled={false} onAction={onAction} />);
    await user.click(screen.getByRole("button", { name: "50% pot" }));
    expect(screen.getByLabelText("Total street bet (chips)")).toHaveValue(375);
    await user.click(screen.getByRole("button", { name: "Raise to 375" }));
    expect(onAction).toHaveBeenCalledWith("raise", 375);
    await user.click(screen.getByRole("button", { name: "Call 100" }));
    expect(onAction).toHaveBeenCalledWith("call");
    await user.click(screen.getByRole("button", { name: "All-in" }));
    expect(onAction).toHaveBeenCalledWith("all_in");
    await user.click(screen.getByRole("button", { name: "Fold" }));
    expect(onAction).toHaveBeenCalledWith("fold");
  });
  it("disables fractional, undersized, oversized, and empty custom wagers", async () => {
    const user = userEvent.setup(), onAction = vi.fn();
    render(<ActionControls legal={gameState().legal} disabled={false} onAction={onAction} />);
    const input = screen.getByLabelText("Total street bet (chips)");
    for (const value of ["199", "10001", "200.5", ""]) {
      await user.clear(input);
      if (value) await user.type(input, value);
      expect(screen.getByRole("button", { name: /^Raise to/ })).toBeDisabled();
    }
    expect(onAction).not.toHaveBeenCalled();
  });
  it("hides raises when betting has not reopened and allows a short all-in", () => {
    render(<ActionControls legal={{ actions: ["fold", "call", "all_in"], to_call: 50,
      min_raise_to: null, max_raise_to: 150, presets: {} }} disabled={false} onAction={vi.fn()} />);
    expect(screen.queryByLabelText("Total street bet (chips)")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All-in" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Check" })).not.toBeInTheDocument();
  });
  it("supports a check or bet and locks every control while submitting", async () => {
    const user = userEvent.setup(), callback = vi.fn();
    const legal = { ...gameState().legal, actions: ["fold", "check", "bet", "all_in"] as const };
    const props = { ...legal, actions: [...legal.actions], to_call: 0 };
    const rendered = render(<ActionControls legal={props} disabled={false} onAction={callback} />);
    await user.click(screen.getByRole("button", { name: "Check" }));
    await user.click(screen.getByRole("button", { name: "Bet 200" }));
    expect(callback).toHaveBeenCalledWith("check");
    expect(callback).toHaveBeenCalledWith("bet", 200);
    rendered.rerender(<ActionControls legal={props} disabled onAction={callback} />);
    screen.getAllByRole("button").forEach(button => expect(button).toBeDisabled());
    expect(screen.getByLabelText("Total street bet (chips)")).toBeDisabled();
  });
});
describe("card visibility", () => {
  it("shows hero cards and renders only card backs for opponents", () => {
    render(<PokerTable game={gameState()} />);
    expect(screen.getByLabelText("As")).toBeInTheDocument();
    expect(screen.getByLabelText("Kh")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Hidden card")).toHaveLength(10);
    expect(screen.getAllByLabelText("Undealt card")).toHaveLength(5);
  });
  it("renders the returned showdown cards and board", () => {
    render(<PokerTable game={completedState()} />);
    expect(screen.queryByLabelText("Hidden card")).not.toBeInTheDocument();
    expect(screen.getByLabelText("2c")).toBeInTheDocument();
    expect(screen.getByText("Settled pot")).toBeInTheDocument();
  });
});
