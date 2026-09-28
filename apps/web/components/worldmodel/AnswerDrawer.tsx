"use client";

// Answer drawer under the path map (specs/005). Shows one answer with the
// evidence that moved the level: contradicted spans in red, demonstrated
// spans underlined green, missing evidence as dashed amber chips; the causes
// that answer contributed; the flip rewrite for it (hypothetical, blind
// re-scored); and "Retry this answer" (real - scored the same way).
import { useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import type { WMCause, WMEvidence, WMFlipRewrite, WMPathPoint, WMRetryResult } from "@/lib/api";
import { STATUS_COLOR, STATUS_TEXT, levelLabel, meanLabel } from "./levels";

interface Segment {
  text: string;
  ev: WMEvidence | null;
}

// Builds a lowercase, whitespace-collapsed copy of the answer plus a map from
// each of its characters back to the original index - the same normalization
// the backend's span guard uses (extractor.span_in_answer), so every span the
// API returns can be found here.
function normalizeWithMap(text: string): { norm: string; map: number[] } {
  let norm = "";
  const map: number[] = [];
  let prevSpace = true;
  for (let i = 0; i < text.length; i++) {
    const isSpace = /\s/.test(text[i]);
    if (isSpace) {
      if (prevSpace) continue;
      norm += " ";
    } else {
      norm += text[i].toLowerCase();
    }
    map.push(i);
    prevSpace = isSpace;
  }
  return { norm, map };
}

// Splits the answer into plain text and cited spans (first occurrence,
// non-overlapping) so each span renders highlighted in place.
function segmentAnswer(answer: string, evidence: WMEvidence[]): Segment[] {
  const marks: { start: number; end: number; ev: WMEvidence }[] = [];
  const { norm, map } = normalizeWithMap(answer);
  for (const ev of evidence) {
    if (!ev.span) continue;
    const needle = normalizeWithMap(ev.span.trim()).norm.trim();
    const idx = needle ? norm.indexOf(needle) : -1;
    if (idx < 0) continue;
    const start = map[idx];
    const end = map[idx + needle.length - 1] + 1;
    if (marks.some((m) => start < m.end && end > m.start)) continue;
    marks.push({ start, end, ev });
  }
  marks.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let pos = 0;
  for (const m of marks) {
    if (m.start > pos) out.push({ text: answer.slice(pos, m.start), ev: null });
    out.push({ text: answer.slice(m.start, m.end), ev: m.ev });
    pos = m.end;
  }
  if (pos < answer.length) out.push({ text: answer.slice(pos), ev: null });
  return out;
}

function polarityWord(ev: WMEvidence): string {
  if (ev.polarity === "contradicted") return "Worked against";
  if (ev.polarity === "absent") return "Missing";
  return "Showed";
}

export default function AnswerDrawer({
  roundId,
  point,
  previousMean,
  causes,
  rewrite,
  retry,
  competencyKey,
  flipAvailable,
  generatingFix,
  onGenerateFix,
  onRetry,
}: {
  roundId: string;
  point: WMPathPoint;
  previousMean: number;
  causes: WMCause[];
  rewrite: WMFlipRewrite | null;
  retry: WMRetryResult | null;
  competencyKey: string;
  flipAvailable: boolean;
  generatingFix: boolean;
  onGenerateFix: () => void;
  onRetry: (text: string) => Promise<void>;
}) {
  const [retryOpen, setRetryOpen] = useState(false);
  const [retryText, setRetryText] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  const segments = segmentAnswer(point.answer, point.evidence);
  const missing = point.evidence.filter((e) => e.polarity === "absent");
  const turnCauses = causes.filter((c) => c.turn_index === point.turn_index);
  const delta = point.level_mean - previousMean;

  async function submitRetry() {
    setRetrying(true);
    setRetryError(null);
    try {
      await onRetry(retryText.trim());
      setRetryOpen(false);
      setRetryText("");
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : "Could not score your retry");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-body font-semibold text-foreground">
          Answer {point.label}
          {point.question ? <span className="font-normal text-muted-foreground"> - {point.question}</span> : null}
        </p>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium" style={{ color: STATUS_COLOR[point.status] }}>
            {STATUS_TEXT[point.status]}
          </span>
          {" · "}
          {Math.abs(delta) < 0.05
            ? `level read held at ${meanLabel(point.level_mean)}`
            : `level read ${delta < 0 ? "dropped" : "rose"} to ${meanLabel(point.level_mean)}`}
        </p>
      </div>

      <div className="mt-4 grid gap-5 md:grid-cols-2">
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-foreground">Your answer</p>
          <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed text-foreground">
            {segments.map((s, i) =>
              s.ev ? (
                <mark
                  key={i}
                  title={`${polarityWord(s.ev)}: ${s.ev.criterion}`}
                  className={
                    s.ev.polarity === "contradicted"
                      ? "rounded bg-status-strong-concern-bg px-0.5 text-foreground ring-1 ring-status-strong-concern"
                      : "bg-transparent text-foreground underline decoration-status-strong-positive decoration-2 underline-offset-4"
                  }
                >
                  {s.text}
                </mark>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )}
          </p>
          {missing.map((m, i) => (
            <p
              key={i}
              className="mt-2 rounded-md border border-dashed border-status-neutral px-2.5 py-1.5 text-sm text-foreground"
            >
              Missing: {m.criterion}
            </p>
          ))}
        </div>

        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-foreground">What changed the score</p>
          {point.evidence.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No evidence on this competency in this answer.</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-sm text-foreground">
              {point.evidence.map((e, i) => (
                <li key={i} className="flex gap-2">
                  <span
                    className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                    style={{
                      background:
                        e.polarity === "contradicted"
                          ? STATUS_COLOR.wrong
                          : e.polarity === "absent"
                            ? STATUS_COLOR.thin
                            : STATUS_COLOR.strong,
                    }}
                  />
                  <span>
                    {polarityWord(e)}: {e.criterion}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {turnCauses.length > 0 && (
            <p className="mt-3 text-sm text-muted-foreground">
              Without this, your level read would end about {turnCauses[0].impact.toFixed(2)} of a level higher.
            </p>
          )}

          {rewrite ? (
            <div className="mt-4 rounded-lg border-2 border-accent/60 bg-accent/5 p-3">
              <p className="text-sm font-semibold text-foreground">Smallest fix</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">+ {rewrite.added_text}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Blind re-score with this addition: {levelLabel(rewrite.current_level)} to{" "}
                {levelLabel(rewrite.projected_level)}
                {rewrite.flipped ? "" : " (not enough on its own to change the level)"}. Hypothetical - a model
                answer for one criterion, not something you said.
              </p>
            </div>
          ) : turnCauses.length > 0 && flipAvailable ? (
            <Button onClick={onGenerateFix} disabled={generatingFix} className="mt-4">
              {generatingFix ? "Finding the smallest fix..." : "Show the smallest fix"}
            </Button>
          ) : null}

          {retry && (
            <p className="mt-3 text-sm text-foreground">
              Your retry: {meanLabel(retry.before[competencyKey] ?? 0)} to{" "}
              <span className="font-semibold">{meanLabel(retry.after[competencyKey] ?? 0)}</span> on this competency.
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setRetryOpen((o) => !o)}
              className="inline-flex items-center rounded-md border border-accent px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent/10"
            >
              {retryOpen ? "Cancel retry" : "Retry this answer"}
            </button>
            <Link
              href={`/reports/${roundId}/replay`}
              className="inline-flex items-center rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong"
            >
              Open in transcript
            </Link>
          </div>
        </div>
      </div>

      {retryOpen && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="text-sm font-medium text-foreground">Answer the same question again</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{point.question}</p>
          <textarea
            value={retryText}
            onChange={(e) => setRetryText(e.target.value)}
            rows={5}
            className="mt-2 w-full rounded-md border border-border bg-background p-3 text-body text-foreground focus:border-border-strong focus:outline-none"
            placeholder="Type your new answer as you would say it in the interview."
          />
          {retryError && <p className="mt-1 text-sm text-status-strong-concern">{retryError}</p>}
          <Button onClick={submitRetry} disabled={retrying || retryText.trim().length < 3} className="mt-2">
            {retrying ? "Scoring..." : "Score my retry"}
          </Button>
        </div>
      )}
    </div>
  );
}
