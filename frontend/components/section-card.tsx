import type { PropsWithChildren } from "react";
import clsx from "clsx";

type SectionCardProps = PropsWithChildren<{
  id?: string;
  title: string;
  description?: string;
  className?: string;
  eyebrow?: string;
}>;

export function SectionCard({
  id,
  title,
  description,
  className,
  eyebrow,
  children
}: SectionCardProps) {
  return (
    <section
      id={id}
      className={clsx("surface-panel scroll-mt-28 p-6", className)}
    >
      <div className="mb-5">
        {eyebrow ? (
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-pine/70">
            {eyebrow}
          </p>
        ) : null}
        <h2 className={clsx("text-xl font-semibold tracking-tight text-ink", eyebrow && "mt-2")}>
          {title}
        </h2>
        {description ? (
          <p className="mt-2 text-sm leading-7 text-ink/65">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
