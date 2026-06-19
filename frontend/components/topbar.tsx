import Link from "next/link";

type TopbarProps = {
  eyebrow?: string;
  title?: string;
  action?: {
    label: string;
    href: string;
  };
};

export function Topbar({
  eyebrow = "Travel Edit OS",
  title = "旅行短视频剪辑导演助手",
  action
}: TopbarProps) {
  return (
    <header className="mx-auto flex w-full max-w-7xl items-start justify-between gap-4 px-6 py-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-pine">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">
          {title}
        </h1>
      </div>
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
    </header>
  );
}
