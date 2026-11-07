const ranks = "AKQJT98765432";
export const rangeMatrix = Array.from(ranks, (a, i) => Array.from(ranks, (b, j) =>
  i === j ? a + b : i < j ? a + b + "s" : b + a + "o"));
export const handClasses = rangeMatrix.flat();
