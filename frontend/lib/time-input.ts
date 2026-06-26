export const TIME_SECONDS_INVALID_MESSAGE = "请输入有效秒数，例如 1.5";

const DECIMAL_PATTERN = /^\d*\.?\d*$/;

export function isPartialTimeSecondsInput(value: string): boolean {
  return value === "" || DECIMAL_PATTERN.test(value);
}

export function parseTimeSeconds(
  value: string,
  options?: { min?: number; max?: number }
): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    return null;
  }

  const min = options?.min ?? 0;
  if (parsed < min) {
    return null;
  }

  if (options?.max !== undefined && parsed > options.max) {
    return null;
  }

  return parsed;
}

export function validateTimeSeconds(
  value: string,
  options?: { min?: number; max?: number; required?: boolean }
): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return options?.required === false ? null : TIME_SECONDS_INVALID_MESSAGE;
  }

  if (parseTimeSeconds(trimmed, options) === null) {
    if (options?.max !== undefined && Number(trimmed) > options.max) {
      return `时间不能超过 ${options.max} 秒。`;
    }
    return TIME_SECONDS_INVALID_MESSAGE;
  }

  return null;
}
