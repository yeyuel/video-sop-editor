"use client";

import clsx from "clsx";
import { useState } from "react";
import {
  isPartialTimeSecondsInput,
  validateTimeSeconds
} from "@/lib/time-input";

type TimeSecondsInputProps = {
  className?: string;
  disabled?: boolean;
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
  className,
  disabled = false,
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

  function handleBlur() {
    const validationError = validateTimeSeconds(value, { min, max, required });
    setFieldError(validationError ?? "");
    onBlur?.();
  }

  return (
    <label className={clsx("block", className)} htmlFor={id}>
      <span className="mb-2 block text-sm text-ink/75">{label}</span>
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
