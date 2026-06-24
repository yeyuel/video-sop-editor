import Link from "next/link";

type TopbarProps = {
  allowLogout?: boolean;
  eyebrow?: string;
  title?: string;
  action?: {
    label: string;
    href: string;
  };
  settingsHref?: string;
};

export function Topbar({
  allowLogout = true,
  eyebrow = "Travel Edit OS",
  title = "旅行短视频剪辑导演助手",
  action,
  settingsHref = "/settings/llm"
}: TopbarProps) {
  return (
    <header className="mx-auto flex w-full max-w-7xl items-start justify-between gap-4 px-6 py-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-pine">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">
          {title}
        </h1>
      </div>
      <div className="flex items-center gap-3">
        {settingsHref ? (
          <Link
            href={settingsHref}
            className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
          >
            LLM 配置
          </Link>
        ) : null}
        {action ? (
          <Link
            href={action.href}
            className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
          >
            {action.label}
          </Link>
        ) : (
          <div className="rounded-full border border-pine/20 bg-white/75 px-4 py-2 text-sm text-ink/75">
            MVP Workspace
          </div>
        )}
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
    </header>
  );
}
