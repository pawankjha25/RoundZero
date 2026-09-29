// Round Zero wordmark lockup (icon + "Round Zero", no tagline) - user-
// supplied brand artwork (2026-09-29), replacing the earlier placeholder
// ring+dot SVG. Shipped as two flattened PNGs rather than one theme-aware
// SVG because the source art is a raster gradient mark, not vector paths:
// `-dark` is the user's own designed dark-mode variant (crisp white
// wordmark, brighter two-tone blue icon), background-removed and re-
// cropped here to line up with the light variant. Swapped via Tailwind's
// `dark:` variant (bound to the app's `.dark` class toggle, not prefers-
// color-scheme - see globals.css's @custom-variant dark).
//
// Deliberately a plain <img>, not next/image: next/image's dev-mode
// on-demand optimizer (GET /_next/image?url=...) cached an optimized
// render of the OLD, clipped source under this same /logo/*.png path and
// kept serving it after the file was overwritten - repeatedly reproduced
// live (2026-09-29) as "the logo doesn't display"/"RO is cutting" even
// once the underlying PNG on disk was already fixed and independently
// verified correct. A plain <img> fetches the static file directly with
// no server-side processing step to go stale, which is worth the next/
// image lint warning (@next/next/no-img-element) for a small, always-
// visible brand asset like this.
export default function Logo({
  className = "",
  size = "sm",
}: {
  className?: string;
  size?: "sm" | "lg";
}) {
  const height = size === "lg" ? "h-10" : "h-6";
  return (
    <span className={"inline-flex items-center " + className}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo/round-zero-lockup.png"
        alt="Round Zero"
        className={height + " w-auto dark:hidden"}
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo/round-zero-lockup-dark.png"
        alt="Round Zero"
        className={"hidden " + height + " w-auto dark:block"}
      />
    </span>
  );
}
