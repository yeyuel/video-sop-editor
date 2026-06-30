import clsx from "clsx";
import type { ReactNode } from "react";

/** Purple highlight for LLM / Vision suggested field values. */
export function aiInputClassName(isSuggested: boolean, base = "input-field") {
  if (isSuggested) {
    return `${base} border-ai/30 bg-ai-soft ring-1 ring-ai-ring/70`;
  }
  return base;
}

type AiFieldLabelProps = {
  children: ReactNode;
  className?: string;
  /** Badge text when suggested; defaults to "AI". Use "Vision" for video analysis. */
  badge?: string;
  suggested?: boolean;
};

export function AiFieldLabel({
  children,
  className,
  badge = "AI",
  suggested = false
}: AiFieldLabelProps) {
  return (
    <span className={clsx("mb-2 flex items-center gap-2 text-sm text-ink/75", className)}>
      {children}
      {suggested ? <span className="badge-ai text-[10px]">{badge}</span> : null}
    </span>
  );
}

type AiSuggestHintProps = {
  badge?: string;
  className?: string;
  count: number;
};

export function AiSuggestHint({ badge = "AI", className, count }: AiSuggestHintProps) {
  if (count <= 0) {
    return null;
  }

  return (
    <p
      className={clsx(
        "rounded-xl border border-ai/20 bg-ai-soft px-4 py-3 text-sm text-ink/75",
        className
      )}
    >
      {badge} 已建议 {count} 个字段（<span className="text-ai">紫色高亮</span>
      ），请确认后保存；手动修改的字段会自动取消高亮。
    </p>
  );
}

export function clearSuggestedField<T extends string>(fields: T[], field: T): T[] {
  return fields.filter((item) => item !== field);
}
