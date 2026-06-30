import Link from "next/link";
import type { ReactNode } from "react";

import { getCurrentSessionUser } from "@/lib/auth-session";

type TopbarProps = {
  allowLogout?: boolean;
  eyebrow?: string;
  title?: string;
  action?: {
    label: string;
    href: string;
  };
  settingsHref?: string;
  manageUsersHref?: string;
};

export async function Topbar({
  allowLogout = true,
  eyebrow = "Travel Edit OS",
  title = "旅行短视频剪辑导演助手",
  action,
  settingsHref = "/settings/llm",
  manageUsersHref
}: TopbarProps) {
  const user = await getCurrentSessionUser();
  const isDirector = user?.role === "director";
  const resolvedSettingsHref = settingsHref && isDirector ? settingsHref : "";
  const resolvedUsersHref =
    manageUsersHref === ""
      ? ""
      : manageUsersHref ?? (isDirector ? "/settings/users" : undefined);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-start justify-between gap-4 px-6 py-4">
        <div className="min-w-0">
          <Link href="/" className="group inline-flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-pine text-[11px] font-bold text-white">
              TE
            </span>
            <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45 group-hover:text-pine">
              {eyebrow}
            </span>
          </Link>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-ink md:text-2xl">
            {title}
          </h1>
        </div>

        <div className="flex flex-col items-end gap-2.5 sm:flex-row sm:items-center">
          {user ? (
            <div className="stat-pill">
              <span className="font-medium text-ink/80">{user.displayName}</span>
              <span className="mx-1.5 text-ink/25">·</span>
              {isDirector ? "导演" : "剪辑"}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Link href="/projects/new" className="btn-primary">
              新建项目
            </Link>
            {action ? (
              <Link href={action.href} className="btn-secondary">
                {action.label}
              </Link>
            ) : null}
            {resolvedUsersHref ? (
              <Link href={resolvedUsersHref} className="btn-ghost">
                用户
              </Link>
            ) : null}
            {resolvedSettingsHref ? (
              <Link href={resolvedSettingsHref} className="btn-ghost">
                LLM
              </Link>
            ) : null}
            {allowLogout ? (
              <form action="/api/auth/logout" method="post">
                <button type="submit" className="btn-ghost text-clay hover:text-clay">
                  退出
                </button>
              </form>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
