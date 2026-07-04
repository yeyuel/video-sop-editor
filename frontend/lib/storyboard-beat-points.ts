import {
  applyBeatOffset,
  filterBeatsForCapcutMode,
  normalizeBeatTimes
} from "@/lib/storyboard-beat-grid";
import type { RhythmPlan } from "@/types/domain";

export function resolveStoryboardBeatPoints(
  rhythmPlan: Pick<
    RhythmPlan,
    "beatCalibration" | "beatPoints" | "rawBeatPoints" | "coarseBeatPoints"
  >,
  options: {
    alignToBeat?: boolean;
    beatMode: string;
    targetDurationSec: number;
  }
): number[] {
  const { alignToBeat = true, beatMode, targetDurationSec } = options;
  if (!alignToBeat || beatMode === "none") {
    return [];
  }

  const rawSource =
    rhythmPlan.rawBeatPoints.length > 0 ? rhythmPlan.rawBeatPoints : rhythmPlan.beatPoints;
  const beatOffsetSec = Number(rhythmPlan.beatCalibration?.beatOffsetSec ?? 0);
  if (rawSource.length > 0) {
    const resolved = filterBeatsForCapcutMode(
      normalizeBeatTimes(rawSource, targetDurationSec),
      beatMode,
      targetDurationSec,
      rhythmPlan.coarseBeatPoints.length > 0 ? rhythmPlan.coarseBeatPoints : undefined
    );
    return applyBeatOffset(resolved, targetDurationSec, beatOffsetSec);
  }

  return applyBeatOffset(rhythmPlan.beatPoints, targetDurationSec, beatOffsetSec);
}

/** 分镜编辑吸附网格 — 与 backend resolve_validation_beat_points / 生成网格一致。 */
export function resolveSnapBeatPointsForSegment(
  rhythmPlan: RhythmPlan,
  segmentBeatMode: string,
  targetDurationSec: number
): number[] {
  const beatMode =
    segmentBeatMode !== "none"
      ? segmentBeatMode
      : rhythmPlan.beatMode !== "none"
        ? rhythmPlan.beatMode
        : "none";

  if (beatMode === "none") {
    return rhythmPlan.beatPoints;
  }

  const resolved = resolveStoryboardBeatPoints(rhythmPlan, {
    beatMode,
    targetDurationSec,
    alignToBeat: true,
  });

  if (resolved.length >= 2) {
    return resolved;
  }

  return rhythmPlan.beatPoints;
}
