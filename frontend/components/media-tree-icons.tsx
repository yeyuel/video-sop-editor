import clsx from "clsx";

type IconProps = {
  className?: string;
};

export function ChevronIcon({ className, open }: IconProps & { open?: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden
      className={clsx(
        "h-3.5 w-3.5 shrink-0 text-ink/35 transition-transform duration-200",
        open && "rotate-90",
        className
      )}
    >
      <path
        d="M6 4l4 4-4 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function FolderIcon({ className, open }: IconProps & { open?: boolean }) {
  if (open) {
    return (
      <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4 shrink-0 text-clay/85", className)}>
        <path
          d="M1.5 4.5A1 1 0 012.5 3.5h3l1.2 1.2h6.8A1 1 0 0114.5 5.7v6.8a1 1 0 01-1 1h-11a1 1 0 01-1-1V4.5z"
          fill="currentColor"
          opacity="0.18"
        />
        <path
          d="M2.5 4h3.2L7 5.3h6.5V12H2.5V4z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.1"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4 shrink-0 text-clay/75", className)}>
      <path
        d="M1.5 4.5A1 1 0 012.5 3.5h3.8L7.5 6h6a1 1 0 011 1v5.5a1 1 0 01-1 1h-11a1 1 0 01-1-1V4.5z"
        fill="currentColor"
        opacity="0.15"
      />
      <path
        d="M2.5 4.5h3.4l1.2 1.5H13v6H2.5v-7.5z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function VideoFileIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4 shrink-0 text-pine", className)}>
      <rect x="2" y="3" width="12" height="10" rx="1.5" fill="currentColor" opacity="0.12" />
      <path
        d="M6.5 6.2v3.6l3.8-1.8-3.8-1.8z"
        fill="currentColor"
        opacity="0.85"
      />
      <rect x="2" y="3" width="12" height="10" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  );
}

export function ImageFileIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4 shrink-0 text-clay", className)}>
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" fill="currentColor" opacity="0.12" />
      <circle cx="5.8" cy="6.2" r="1.1" fill="currentColor" opacity="0.7" />
      <path
        d="M3.5 11l2.6-2.4 1.8 1.6L10.5 7 13 11"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  );
}

export function AudioFileIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4 shrink-0 text-pine/70", className)}>
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" fill="currentColor" opacity="0.12" />
      <path
        d="M6 10.5V5.8l4.2-1.2v5.9M6 10.5a1.2 1.2 0 102.4 0 1.2 1.2 0 00-2.4 0zm4.2-.3a1.2 1.2 0 102.4 0 1.2 1.2 0 00-2.4 0z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.05"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  );
}

export function FileKindIcon({
  kind,
  open,
  isDirectory
}: {
  kind?: string | null;
  open?: boolean;
  isDirectory?: boolean;
}) {
  if (isDirectory) {
    return <FolderIcon open={open} />;
  }
  if (kind === "image") {
    return <ImageFileIcon />;
  }
  if (kind === "audio") {
    return <AudioFileIcon />;
  }
  return <VideoFileIcon />;
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className={clsx("h-4 w-4", className)}>
      <circle cx="7" cy="7" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M10.2 10.2L13 13" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
