import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import { Trainer } from "../components/Trainer";
import { completedState, gameState } from "./fixtures";
describe("trainer interactions", () => {
  it("starts a hand, submits a hero action, shows settlement, and starts again", async () => {
    const user = userEvent.setup();
    const mock = vi.spyOn(api, "requestGame").mockRejectedValueOnce(new api.ApiError("No session", 404))
      .mockResolvedValueOnce(gameState()).mockResolvedValueOnce(completedState())
      .mockResolvedValueOnce({ ...gameState(), hand_number: 2, hand_id: "next" });
    render(<Trainer />);
    await user.click(await screen.findByRole("button", { name: "New Hand" }));
    await screen.findByLabelText("As");
    expect(screen.getByRole("button", { name: "New Hand" })).toBeDisabled();
    expect(screen.getByRole("list", { name: "Action history" })).toHaveTextContent("Morgan");
    await user.click(screen.getByRole("button", { name: "Call 100" }));
    expect(mock).toHaveBeenNthCalledWith(3, "/api/game/actions",
      { hand_id: "test-hand", revision: 0, action: "call" });
    expect(await screen.findByLabelText("Hand result")).toHaveTextContent("+500 chips");
    await user.click(screen.getByRole("button", { name: "New Hand" }));
    await screen.findByText("#2");
    expect(mock).toHaveBeenLastCalledWith("/api/games", {});
  });
  it("restores a hand on reload without dealing a second hand", async () => {
    const mock = vi.spyOn(api, "requestGame").mockResolvedValue(gameState());
    render(<Trainer />);
    await screen.findByLabelText("As");
    expect(mock).toHaveBeenCalledTimes(1);
    expect(mock).toHaveBeenCalledWith("/api/game");
  });
  it("shows a server error and recovers the authoritative state", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "requestGame").mockResolvedValueOnce(gameState())
      .mockRejectedValueOnce(new api.ApiError("Hand has changed", 409))
      .mockResolvedValueOnce(completedState());
    render(<Trainer />);
    await user.click(await screen.findByRole("button", { name: "Fold" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Hand has changed");
    expect(await screen.findByLabelText("Hand result")).toBeInTheDocument();
  });
  it("locks the table during submission to prevent repeated clicks", async () => {
    const user = userEvent.setup();
    let resolve!: (state: ReturnType<typeof gameState>) => void;
    const pending = new Promise<ReturnType<typeof gameState>>(r => { resolve = r; });
    const mock = vi.spyOn(api, "requestGame").mockResolvedValueOnce(gameState()).mockReturnValueOnce(pending);
    render(<Trainer />);
    await user.click(await screen.findByRole("button", { name: "Call 100" }));
    expect(screen.getByRole("button", { name: "Call 100" })).toBeDisabled();
    expect(mock).toHaveBeenCalledTimes(2);
    resolve(completedState());
    await screen.findByLabelText("Hand result");
  });
  it("blocks decisions after failed recovery until refresh succeeds", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "requestGame").mockResolvedValueOnce(gameState())
      .mockRejectedValueOnce(new api.ApiError("Offline", 0)).mockRejectedValueOnce(new api.ApiError("Offline", 0))
      .mockResolvedValueOnce(gameState());
    render(<Trainer />);
    await user.click(await screen.findByRole("button", { name: "Call 100" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh table" })).toBeEnabled());
    expect(screen.getByRole("button", { name: "Call 100" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Refresh table" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Call 100" })).toBeEnabled();
  });
  it("handles a failed initial load and an expired session", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "requestGame").mockRejectedValueOnce(new api.ApiError("Backend unavailable", 502))
      .mockRejectedValueOnce(new api.ApiError("Expired", 404));
    render(<Trainer />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
    expect(screen.getByRole("button", { name: "New Hand" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Refresh table" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "New Hand" })).toBeEnabled());
  });
});
