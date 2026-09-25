import { describe, expect, it } from "vitest";

import {
  formatDuration,
  MS_PER_MINUTE,
  MS_PER_SECOND,
} from "@/lib/formatDuration";

describe("formatDuration", () => {
  it("shows milliseconds below one second", () => {
    expect(formatDuration(0)).toBe("0 ms");
    expect(formatDuration(MS_PER_SECOND - 1)).toBe(`${MS_PER_SECOND - 1} ms`);
  });

  it("promotes to seconds at one second and above", () => {
    expect(formatDuration(MS_PER_SECOND)).toBe("1 s");
    expect(formatDuration(MS_PER_SECOND * 1.5)).toBe("1.5 s");
  });

  it("promotes to minutes at one minute and above", () => {
    expect(formatDuration(MS_PER_MINUTE)).toBe("1 min");
    expect(formatDuration(MS_PER_MINUTE * 1.5)).toBe("1.5 min");
  });

  it("drops a trailing .0 so whole values read cleanly", () => {
    expect(formatDuration(MS_PER_SECOND * 2)).toBe("2 s");
    expect(formatDuration(MS_PER_MINUTE * 3)).toBe("3 min");
  });

  it("rounds sub-millisecond noise to whole milliseconds", () => {
    expect(formatDuration(12.4)).toBe("12 ms");
  });

  it("returns an em dash for invalid input", () => {
    expect(formatDuration(-1)).toBe("—");
    expect(formatDuration(Number.NaN)).toBe("—");
  });
});
