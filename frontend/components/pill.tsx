import clsx from "clsx";
import Link from "next/link";

type PillProps = {
  label: string;
  href?: string;
  active?: boolean;
};

export function Pill({ label, href, active = false }: PillProps) {
  const className = clsx(
    "inline-flex items-center rounded-full px-4 py-2 text-sm font-medium transition",
    active
      ? "bg-pine text-white shadow-sm"
      : "bg-mist text-pine hover:bg-pine hover:text-white"
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {label}
      </Link>
    );
  }

  return <span className={className}>{label}</span>;
}
