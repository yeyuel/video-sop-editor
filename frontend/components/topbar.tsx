import Link from "next/link";

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
    <header className="mx-auto flex w-full max-w-7xl items-start justify-between gap-4 px-6 py-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-pine">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">
          {title}
        </h1>
      </div>
      <div className="flex flex-col items-end gap-3 sm:flex-row sm:items-center">
        {user ? (
          <div className="rounded-full border border-pine/15 bg-white/85 px-4 py-2 text-xs text-ink/70">
            {user.displayName} · {isDirector ? "导演" : "剪辑"}
            {!isDirector ? " · 项目内编辑" : " · 全量能力"}
          </div>
        ) : null}
        <div className="flex items-center gap-3">
        <Link
          href="/projects/new"
          className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
        >
          新建项目
        </Link>
        {action ? (
          <Link
            href={action.href}
            className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
          >
            {action.label}
          </Link>
        ) : null}
        {resolvedUsersHref ? (
          <Link
            href={resolvedUsersHref}
            className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
          >
            用户管理
          </Link>
        ) : null}
        {resolvedSettingsHref ? (
          <Link
            href={resolvedSettingsHref}
            className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
          >
            LLM 配置
          </Link>
        ) : null}
        {allowLogout ? (
          <form action="/api/auth/logout" method="post">
            <button
              type="submit"
              className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
            >
              退出登录
            </button>
          </form>
        ) : null}
        </div>
      </div>
    </header>
  );
}
