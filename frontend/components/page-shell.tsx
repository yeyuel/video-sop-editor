import Link from "next/link";
import clsx from "clsx";
import type { ReactNode } from "react";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

type PageShellProps = {
  breadcrumbs?: BreadcrumbItem[];
  eyebrow?: string;
  title: string;
  description?: string;
  aside?: ReactNode;
  children?: ReactNode;
  className?: string;
};

export function PageShell({
  breadcrumbs,
  eyebrow,
  title,
  description,
  aside,
  children,
  className
}: PageShellProps) {
  return (
    <div className={clsx("surface-hero", className)}>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <nav aria-label="面包屑" className="mb-5 flex flex-wrap items-center gap-1.5 text-sm">
          {breadcrumbs.map((item, index) => {
            const isLast = index === breadcrumbs.length - 1;
            return (
              <span key={`${item.label}-${index}`} className="inline-flex items-center gap-1.5">
                {index > 0 ? <span className="text-ink/25">/</span> : null}
                {item.href && !isLast ? (
                  <Link
                    href={item.href}
                    className="text-ink/45 transition hover:text-pine"
                  >
                    {item.label}
                  </Link>
                ) : (
                  <span className={isLast ? "font-medium text-ink/80" : "text-ink/50"}>
                    {item.label}
                  </span>
                )}
              </span>
            );
          })}
        </nav>
      ) : null}

      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? (
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-pine/80">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{title}</h2>
          {description ? (
            <p className="mt-3 text-sm leading-7 text-ink/65">{description}</p>
          ) : null}
        </div>
        {aside ? <div className="shrink-0">{aside}</div> : null}
      </div>

      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  );
}
