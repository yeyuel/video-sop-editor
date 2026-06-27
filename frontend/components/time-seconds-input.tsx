"use client";

import clsx from "clsx";
import { useState } from "react";
import { snapTimeInputToBeat } from "@/lib/beat-snap";
import {
  isPartialTimeSecondsInput,
  validateTimeSeconds
} from "@/lib/time-input";

type TimeSecondsInputProps = {
  beatPoints?: number[];
  beatSnapMin?: number;
  className?: string;
  disabled?: boolean;
  enableBeatSnap?: boolean;
  id?: string;
  label: string;
  max?: number;
  min?: number;
  onBlur?: () => void;
  onValueChange: (value: string) => void;
  required?: boolean;
  value: string;
};

export function TimeSecondsInput({
  beatPoints = [],
  beatSnapMin,
  className,
  disabled = false,
  enableBeatSnap = false,
  id,
  label,
  max,
  min = 0,
  onBlur,
  onValueChange,
  required = true,
  value
}: TimeSecondsInputProps) {
  const [fieldError, setFieldError] = useState("");
  const canSnap = enableBeatSnap && beatPoints.length >= 2;

  function resolveSnappedValue(currentValue: string): string {
    if (!canSnap) {
      return currentValue;
    }

    const snapped = snapTimeInputToBeat(currentValue, beatPoints, {
      min: beatSnapMin ?? min,
      max,
      required
    });
    return snapped ?? currentValue;
  }

  function applyBeatSnap() {
    if (!canSnap) {
      return;
    }

    const snapped = resolveSnappedValue(value);
    if (snapped !== value) {
      onValueChange(snapped);
    }
    setFieldError("");
  }

  function handleBlur() {
    const nextValue = resolveSnappedValue(value);
    if (nextValue !== value) {
      onValueChange(nextValue);
    }

    const validationError = validateTimeSeconds(nextValue, { min, max, required });
    setFieldError(validationError ?? "");
    onBlur?.();
  }

  return (
    <label className={clsx("block", className)} htmlFor={id}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm text-ink/75">{label}</span>
        {canSnap ? (
          <button
            type="button"
            disabled={disabled}
            onClick={applyBeatSnap}
            className="text-xs font-medium text-pine transition hover:text-pine/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            吸附到最近节拍
          </button>
        ) : null}
      </div>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        disabled={disabled}
        value={value}
        placeholder="例如 1.5"
        onChange={(event) => {
          const nextValue = event.target.value;
          if (isPartialTimeSecondsInput(nextValue)) {
            onValueChange(nextValue);
            if (fieldError) {
              setFieldError("");
            }
          }
        }}
        onBlur={handleBlur}
        className={clsx(
          "w-full rounded-2xl border bg-white px-4 py-3 outline-none transition focus:border-pine",
          fieldError ? "border-clay/40" : "border-pine/30"
        )}
      />
      {fieldError ? <p className="mt-2 text-xs text-clay">{fieldError}</p> : null}
    </label>
  );
}
