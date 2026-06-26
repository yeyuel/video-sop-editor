"use client";

import clsx from "clsx";

type BlockingNoticeProps = {
  description: string;
  title: string;
  visible: boolean;
};

type ToastNoticeProps = {
  message: string;
  title: string;
  tone?: "success" | "error" | "warning";
  visible: boolean;
};

export function BlockingNotice({
  description,
  title,
  visible
}: BlockingNoticeProps) {
  if (!visible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 px-6 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-[28px] border border-white/65 bg-white/90 p-6 shadow-[0_28px_80px_rgba(25,34,41,0.14)]">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-mist">
          <div className="async-orbit relative h-7 w-7">
            <span className="absolute inset-0 rounded-full border-2 border-pine/20" />
            <span className="absolute inset-[3px] rounded-full border-2 border-transparent border-t-pine border-r-pine" />
          </div>
        </div>
        <h3 className="mt-5 text-center text-xl font-semibold text-ink">{title}</h3>
        <p className="mt-2 text-center text-sm leading-6 text-ink/65">{description}</p>
        <div className="mt-5 flex items-center justify-center gap-1.5">
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/35 [animation-delay:-0.2s]" />
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/55 [animation-delay:-0.1s]" />
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/75" />
        </div>
      </div>
    </div>
  );
}

export function ToastNotice({
  message,
  title,
  tone = "success",
  visible
}: ToastNoticeProps) {
  if (!visible) {
    return null;
  }

  const isSuccess = tone === "success";
  const isWarning = tone === "warning";

  return (
    <div className="pointer-events-none fixed right-6 top-6 z-50 w-full max-w-sm">
      <div
        className={clsx(
          "toast-enter rounded-[24px] border px-5 py-4 shadow-[0_24px_64px_rgba(25,34,41,0.14)] backdrop-blur-md",
          isSuccess
            ? "border-pine/15 bg-white/92"
            : isWarning
              ? "border-sand/30 bg-white/94"
              : "border-clay/20 bg-white/94"
        )}
      >
        <div className="flex items-start gap-3">
          <div
            className={clsx(
              "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-semibold",
              isSuccess
                ? "bg-mist text-pine"
                : isWarning
                  ? "bg-sand text-ink/75"
                  : "bg-[#fff1ea] text-clay"
            )}
          >
            {isSuccess ? "✓" : isWarning ? "!" : "!"}
          </div>
          <div className="min-w-0">
            <p className="text-base font-semibold text-ink">{title}</p>
            <p className="mt-1 text-sm leading-6 text-ink/70">{message}</p>
          </div>
        </div>
        <div
          className={clsx(
            "mt-4 h-1.5 overflow-hidden rounded-full",
            isSuccess ? "bg-mist" : isWarning ? "bg-sand/70" : "bg-[#f9dfd3]"
          )}
        >
          <div
            className={clsx(
              "toast-progress h-full rounded-full",
              isSuccess ? "bg-pine" : isWarning ? "bg-sand" : "bg-clay"
            )}
          />
        </div>
      </div>
    </div>
  );
}
