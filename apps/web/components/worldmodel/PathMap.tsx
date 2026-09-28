"use client";

// Interview path map (specs/005, design doc "Progress tab"). One node per
// candidate answer, plotted at the level the world model believed after that
// answer, with a +/- 1 std confidence band. Node color = what that answer's
// evidence did (strong / thin / went wrong / none). The answer where the
// level dropped most is ringed and labelled.
//
// Two counterfactual branches, kept visually distinct so projected and real
// improvement are never mixed:
//  - dashed: a flip rewrite (HYPOTHETICAL) - from the answer before the fixed
//    one, through the fixed answer, to the projected outcome. It draws no
//    invented turns after the fix; the projection is the blind re-score of
//    the transcript with only that answer edited.
//  - solid: the candidate's own retry (REAL).
//
// Hand-rolled SVG (not recharts) because the band, branches and outcome
// column are one custom composition; colors are the app's CSS tokens.
import type { WMCompetencyDiagnosis, WMFlipRewrite, WMRetryResult } from "@/lib/api";
import { LEVEL_LABELS, STATUS_COLOR, meanLabel } from "./levels";

const W = 760;
const H = 250;
const TOP = 28;
const ROW = 50; // px per level step
const X0 = 124;
const X1 = 590;
const OUT_X = 630;

const ACCENT = "var(--color-accent)";
const AXIS = "var(--color-border-strong)";
const GRID = "var(--color-border)";
const INK = "var(--color-foreground)";
const QUIET = "var(--color-muted-foreground)";
const BAND = "var(--color-muted)";

function y(mean: number): number {
  const m = Math.max(0, Math.min(3, mean));
  return TOP + (3 - m) * ROW;
}

function diamond(cx: number, cy: number, r = 7): string {
  return `M${cx} ${cy - r}L${cx + r} ${cy}L${cx} ${cy + r}L${cx - r} ${cy}Z`;
}

export default function PathMap({
  diagnosis,
  rewrite,
  retry,
  selectedTurn,
  onSelect,
}: {
  diagnosis: WMCompetencyDiagnosis;
  rewrite: WMFlipRewrite | null;
  retry: WMRetryResult | null;
  selectedTurn: number | null;
  onSelect: (turnIndex: number) => void;
}) {
  const path = diagnosis.path;
  const n = path.length;
  const xs = path.map((_, i) => (n === 1 ? (X0 + X1) / 2 : X0 + (i * (X1 - X0)) / (n - 1)));
  const xByTurn = new Map(path.map((p, i) => [p.turn_index, xs[i]]));
  const showEvery = n > 16 ? 2 : 1;

  const upper = path.map((p, i) => `${xs[i]},${y(p.level_mean + p.level_std)}`);
  const lower = path.map((p, i) => `${xs[i]},${y(p.level_mean - p.level_std)}`).reverse();
  const actualLine = [...path.map((p, i) => `${xs[i]},${y(p.level_mean)}`), `${OUT_X},${y(diagnosis.final_mean)}`];

  function branchFrom(turnIndex: number): { x: number; y: number } {
    const i = path.findIndex((p) => p.turn_index === turnIndex);
    if (i > 0) return { x: xs[i - 1], y: y(path[i - 1].level_mean) };
    return { x: xs[0] - 24, y: y(path[0]?.level_mean ?? diagnosis.final_mean) };
  }

  const wentWrongX = diagnosis.went_wrong_turn != null ? xByTurn.get(diagnosis.went_wrong_turn) : undefined;
  const wentWrongPoint = path.find((p) => p.turn_index === diagnosis.went_wrong_turn);

  const retryAfter = retry ? retry.after[diagnosis.competency] : undefined;
  const showFix = !!rewrite && xByTurn.has(rewrite.turn_index);
  const showRetry = !!retry && retryAfter !== undefined && xByTurn.has(retry.turn_index);

  // Outcome-column labels (actual / projected / retry) can land on the same
  // level - lay them out top to bottom with a minimum gap so they never overlap.
  const labelY: Record<string, number> = {};
  {
    const items: { key: string; y: number; h: number }[] = [
      { key: "actual", y: y(diagnosis.final_mean) + 4, h: 16 },
    ];
    if (showFix && rewrite) items.push({ key: "fix", y: y(rewrite.projected_mean) - 2, h: 30 });
    if (showRetry && retryAfter !== undefined) items.push({ key: "retry", y: y(retryAfter) + 4, h: 16 });
    items.sort((a, b) => a.y - b.y);
    let floor = -Infinity;
    for (const it of items) {
      const placed = Math.max(it.y, floor);
      labelY[it.key] = placed;
      floor = placed + it.h + 4;
    }
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Interview path map for ${diagnosis.label}: ends at ${meanLabel(diagnosis.final_mean)}`}
    >
      <defs>
        <marker id="pm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0L10 5L0 10z" fill={QUIET} />
        </marker>
      </defs>

      {/* level grid + labels */}
      {LEVEL_LABELS.map((label, i) => (
        <g key={label}>
          <line x1={X0 - 16} x2={OUT_X} y1={y(i)} y2={y(i)} stroke={GRID} />
          <text x={12} y={y(i) + 4} fontSize={12} fill={QUIET}>
            {label}
          </text>
        </g>
      ))}

      {/* confidence band */}
      {n > 0 && <polygon points={[...upper, ...lower].join(" ")} fill={BAND} opacity={0.9} />}

      {/* actual path to the outcome */}
      {n > 0 && <polyline points={actualLine.join(" ")} fill="none" stroke={AXIS} strokeWidth={2} />}
      <path d={diamond(OUT_X, y(diagnosis.final_mean))} fill={QUIET} />
      <text x={OUT_X + 14} y={labelY.actual} fontSize={12} fontWeight={600} fill={INK}>
        Actual: {diagnosis.abstained ? "unclear" : meanLabel(diagnosis.final_mean)}
      </text>

      {/* hypothetical fix branch (dashed) */}
      {showFix && rewrite && (
        <g aria-label="Projected outcome with the fix (hypothetical)">
          {(() => {
            const from = branchFrom(rewrite.turn_index);
            const fx = xByTurn.get(rewrite.turn_index) as number;
            const py = y(rewrite.projected_mean);
            return (
              <>
                <polyline
                  points={`${from.x},${from.y} ${fx},${py} ${OUT_X},${py}`}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                />
                <circle cx={fx} cy={py} r={6} fill="var(--color-surface)" stroke={ACCENT} strokeWidth={2} />
                <path d={diamond(OUT_X, py)} fill={ACCENT} />
                <text x={OUT_X + 14} y={labelY.fix} fontSize={12} fontWeight={600} fill={INK}>
                  Projected: {meanLabel(rewrite.projected_mean)}
                </text>
                <text x={OUT_X + 14} y={labelY.fix + 15} fontSize={11} fill={QUIET}>
                  with the fix
                </text>
              </>
            );
          })()}
        </g>
      )}

      {/* real retry branch (solid) */}
      {showRetry && retry && retryAfter !== undefined && (
        <g aria-label="Your retry (real)">
          {(() => {
            const from = branchFrom(retry.turn_index);
            const rx = xByTurn.get(retry.turn_index) as number;
            const ry = y(retryAfter);
            return (
              <>
                <polyline points={`${from.x},${from.y} ${rx},${ry} ${OUT_X},${ry}`} fill="none" stroke={ACCENT} strokeWidth={2.5} />
                <circle cx={rx} cy={ry} r={6} fill={ACCENT} />
                <path d={diamond(OUT_X, ry)} fill={ACCENT} />
                <text x={OUT_X + 14} y={labelY.retry} fontSize={12} fontWeight={600} fill={INK}>
                  Retry: {meanLabel(retryAfter)}
                </text>
              </>
            );
          })()}
        </g>
      )}

      {/* answer nodes */}
      {path.map((p, i) => {
        const selected = p.turn_index === selectedTurn;
        return (
          <g
            key={p.turn_index}
            role="button"
            tabIndex={0}
            aria-label={`Answer ${p.label}: ${meanLabel(p.level_mean)} after this answer`}
            onClick={() => onSelect(p.turn_index)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onSelect(p.turn_index);
            }}
            style={{ cursor: "pointer" }}
          >
            <circle cx={xs[i]} cy={y(p.level_mean)} r={14} fill="transparent" />
            <circle cx={xs[i]} cy={y(p.level_mean)} r={6.5} fill={STATUS_COLOR[p.status]} />
            {selected && <circle cx={xs[i]} cy={y(p.level_mean)} r={11} fill="none" stroke={INK} strokeWidth={1.5} />}
            {i % showEvery === 0 && (
              <text
                x={xs[i]}
                y={H - 22}
                fontSize={11}
                textAnchor="middle"
                fontWeight={selected ? 700 : 400}
                fill={selected ? INK : QUIET}
              >
                {p.label}
              </text>
            )}
          </g>
        );
      })}

      {/* where it went wrong */}
      {wentWrongX !== undefined && wentWrongPoint && (
        <g>
          <circle cx={wentWrongX} cy={y(wentWrongPoint.level_mean)} r={11} fill="none" stroke="var(--color-status-strong-concern)" strokeWidth={1.5} />
          <text
            x={wentWrongX}
            y={Math.min(y(wentWrongPoint.level_mean) + 30, y(0) + 20)}
            fontSize={12}
            fontWeight={600}
            textAnchor="middle"
            fill={INK}
          >
            where it went wrong
          </text>
        </g>
      )}

      <text x={X0} y={H - 6} fontSize={11} fill={QUIET}>
        Answers, in order
      </text>
    </svg>
  );
}
