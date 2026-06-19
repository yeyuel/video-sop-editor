import type { PropsWithChildren } from "react";
import clsx from "clsx";

type SectionCardProps = PropsWithChildren<{
  id?: string;
  title: string;
  description?: string;
  className?: string;
}>;

export function SectionCard({
  id,
  title,
  description,
  className,
  children
}: SectionCardProps) {
  return (
    <section
      id={id}
      className={clsx(
        "scroll-mt-24 rounded-xl2 border border-black/5 bg-white/90 p-6 shadow-card backdrop-blur",
        className
      )}
    >
      <div className="mb-4">
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm leading-6 text-ink/70">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
