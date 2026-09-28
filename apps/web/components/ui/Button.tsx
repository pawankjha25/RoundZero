import Link from "next/link";
import type { MouseEventHandler, ReactNode } from "react";

// Shared primary-action button/link (DESIGN.md > Components > Buttons).
// Before this existed every primary CTA was styled inline per page, which
// is exactly how the app ended up with rounded-md/rounded-lg drift across
// otherwise-identical buttons (see the design pass that added DESIGN.md).
// Renders a Next.js <Link> when given `href`, a real <button> otherwise -
// same visual treatment either way, since to the user both are "the button
// that does the primary thing on this screen."
//
// Scope: the page-level primary-CTA tier only (the "default"/"large" sizes
// below). Compact/secondary action buttons and external (target="_blank")
// links are intentionally not migrated to this component yet - see
// DESIGN.md's Components > Buttons note for why.

const BASE =
  "inline-flex items-center justify-center rounded-lg bg-accent text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const SIZE = {
  default: "px-4 py-2 text-sm font-medium",
  large: "px-5 py-3 text-base font-semibold",
} as const;

type ButtonProps = {
  children: ReactNode;
  size?: keyof typeof SIZE;
  fullWidth?: boolean;
  className?: string;
  href?: string;
  type?: "button" | "submit" | "reset";
  onClick?: MouseEventHandler;
  disabled?: boolean;
};

export default function Button({
  children,
  size = "default",
  fullWidth = false,
  className = "",
  href,
  type = "button",
  onClick,
  disabled,
}: ButtonProps) {
  const classes = [BASE, SIZE[size], fullWidth ? "w-full" : "", className].filter(Boolean).join(" ");

  if (href) {
    return (
      <Link href={href} className={classes} onClick={onClick}>
        {children}
      </Link>
    );
  }

  return (
    <button type={type} onClick={onClick} disabled={disabled} className={classes}>
      {children}
    </button>
  );
}
