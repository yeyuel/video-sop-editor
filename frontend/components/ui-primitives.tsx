"use client";

import clsx from "clsx";
import type { ReactNode } from "react";
import { BlockingNotice } from "@/components/async-status";

type ValidationIssuesPanelProps = {
  className?: string;
  issues: string[];
  title?: string;
};

export function ValidationIssuesPanel({
  className,
  issues,
  title = "校验摘要"
}: ValidationIssuesPanelProps) {
  if (issues.length === 0) {
    return null;
  }

  return (
    <div
      className={clsx(
        "rounded-2xl border border-sand/40 bg-sand/35 px-4 py-4 text-sm text-ink/75",
        className
      )}
    >
      <p className="font-medium text-ink">{title}</p>
      <ul className="mt-3 space-y-2">
        {issues.map((issue, index) => (
          <li key={`${index}-${issue}`} className="flex gap-2 leading-6">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-clay/70" />
            <span>{issue}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

type EmptyStateProps = {
  children?: ReactNode;
  message: string;
};

type InlineErrorBannerProps = {
  className?: string;
  message: string;
};

type ConfirmDialogProps = {
  cancelLabel?: string;
  confirmLabel?: string;
  confirmTone?: "danger" | "primary";
  description: string;
  error?: string;
  isPending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  subtitle?: string;
  title: string;
};

export function EmptyState({ children, message }: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-dashed border-pine/20 bg-white px-4 py-8 text-center text-sm text-ink/60">
      <p>{message}</p>
      {children ? <div className="mt-4 flex justify-center gap-3">{children}</div> : null}
    </div>
  );
}

export function InlineErrorBanner({ className, message }: InlineErrorBannerProps) {
  if (!message) {
    return null;
  }

  return (
    <div
      className={clsx(
        "rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay",
        className
      )}
    >
      {message}
    </div>
  );
}

export function ConfirmDialog({
  cancelLabel = "取消",
  confirmLabel = "确认",
  confirmTone = "primary",
  description,
  error,
  isPending = false,
  onCancel,
  onConfirm,
  open,
  subtitle,
  title
}: ConfirmDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title="正在处理"
        description="请稍候，操作完成前请不要关闭页面。"
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-6">
        <div className="w-full max-w-md rounded-xl2 border border-black/5 bg-white p-6 shadow-card">
          {subtitle ? (
            <p className="text-xs uppercase tracking-[0.22em] text-clay/80">{subtitle}</p>
          ) : null}
          <h3 className="mt-3 text-2xl font-semibold text-ink">{title}</h3>
          <p className="mt-3 text-sm leading-6 text-ink/70">{description}</p>
          {error ? <InlineErrorBanner className="mt-3" message={error} /> : null}
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onConfirm}
              disabled={isPending}
              className={clsx(
                "inline-flex rounded-full px-5 py-3 text-sm font-medium text-white transition disabled:cursor-not-allowed disabled:opacity-60",
                confirmTone === "danger"
                  ? "bg-clay hover:bg-clay/90"
                  : "bg-pine hover:bg-pine/90"
              )}
            >
              {isPending ? "处理中..." : confirmLabel}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={isPending}
              className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
            >
              {cancelLabel}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
