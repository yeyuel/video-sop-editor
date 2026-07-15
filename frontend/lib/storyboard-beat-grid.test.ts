import { describe, expect, it } from "vitest";

import {
  applyBeatCalibration,
  applyBeatOffset,
  filterBeatsForCapcutMode
} from "@/lib/storyboard-beat-grid";

describe("filterBeatsForCapcutMode", () => {
  it("keeps all fine beats for beat_2", () => {
    const allBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3];
    expect(filterBeatsForCapcutMode(allBeats, "beat_2", 3)).toEqual([
      0, 0.5, 1, 1.5, 2, 2.5, 3
    ]);
  });

  it("applies calibration offset within target duration", () => {
    expect(applyBeatOffset([0, 1, 2, 3], 3, 0.2)).toEqual([0, 0.2, 1.2, 2.2, 3]);
  });

  it("applies calibration scale and offset within target duration", () => {
    expect(applyBeatCalibration([0, 1, 2, 3], 3.5, 0.1, 1.05)).toEqual([
      0, 0.1, 1.15, 2.2, 3.25, 3.5
    ]);
  });

  it("uses coarse grid for beat_1 when provided", () => {
    const fineBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];
    const coarseBeats = [0, 1, 2, 3, 4];
    expect(filterBeatsForCapcutMode(fineBeats, "beat_1", 4, coarseBeats)).toEqual([
      0, 1, 2, 3, 4
    ]);
  });

  it("strides fine beats for beat_1 without coarse grid", () => {
    const allBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];
    expect(filterBeatsForCapcutMode(allBeats, "beat_1", 4)).toEqual([0, 1, 2, 3, 4]);
  });

  it("keeps downbeats for strong_weak with coarse grid", () => {
    const fineBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];
    const coarseBeats = [0, 1, 2, 3, 4];
    expect(filterBeatsForCapcutMode(fineBeats, "strong_weak", 4, coarseBeats)).toEqual([
      0, 2, 4
    ]);
  });
});

describe("resolveStoryboardBeatPoints parity", () => {
  it("matches generation grid for beat_2 raw beats", async () => {
    const { resolveStoryboardBeatPoints } = await import("@/lib/storyboard-beat-points");
    const rhythmPlan = {
      beatPoints: [0, 2, 4],
      rawBeatPoints: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4],
      coarseBeatPoints: [0, 1, 2, 3, 4],
      beatCalibration: {},
    };

    expect(
      resolveStoryboardBeatPoints(rhythmPlan, {
        beatMode: "beat_2",
        targetDurationSec: 4,
      })
    ).toEqual([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]);
  });

  it("applies calibration offset and scale to storyboard snap grid", async () => {
    const { resolveStoryboardBeatPoints } = await import("@/lib/storyboard-beat-points");
    const rhythmPlan = {
      beatPoints: [0, 1, 2, 3],
      rawBeatPoints: [0, 1, 2, 3],
      coarseBeatPoints: [],
      beatCalibration: { beatOffsetSec: 0.1, beatScale: 1.05 },
    };

    expect(
      resolveStoryboardBeatPoints(rhythmPlan, {
        beatMode: "beat_2",
        targetDurationSec: 3.5,
      })
    ).toEqual([0, 0.1, 1.15, 2.2, 3.25, 3.5]);
  });
});
