import { expect, it } from "vitest";
import { selectIndex, practiceUrl, spot } from "../lib/training";
it("selects deterministically within bounds and preserves exact exercise identity", () => {
  expect(selectIndex(10, 42)).toBe(2);
  expect(selectIndex(1, 0xffffffff)).toBe(0);
  expect(
    spot({
      solution_id: "s",
      scenario_id: "public",
      version: "v1",
      combo: "KhQh",
    }),
  ).toBe("public/KhQh/v1");
  expect(practiceUrl("s", "public", "KhQh", "bet@275", "unique")).toContain(
    "action=bet%40275&review=unique",
  );
});
