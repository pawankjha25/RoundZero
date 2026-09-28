"use client";

// Conversational core shared by every workspace type (specs/003-premium-
// uiux-redesign sections 9-10): AI interviewer presence up top, transcript
// below it (accessible but visually secondary per the spec - not hidden),
// then the reply form. Same sendMessage()/optimistic-turn state as before
// this pass - only the layout and visual system changed, not the request
// flow, so getRound()/submitRound() callers elsewhere are unaffected.
import { useEffect, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { sendMessage, type RoundSummary, type Turn } from "@/lib/api";
import AIInterviewerPresence, { INTERVIEWER_NAME } from "./AIInterviewerPresence";
import VoiceControls from "./VoiceControls";

interface AIInterviewerPanelProps {
  round: RoundSummary;
  transcript: Turn[];
  setTranscript: Dispatch<SetStateAction<Turn[]>>;
  setRound: Dispatch<SetStateAction<RoundSummary | null>>;
  setSecondsLeft: Dispatch<SetStateAction<number>>;
  ending: boolean;
}

export default function AIInterviewerPanel({
  round,
  transcript,
  setTranscript,
  setRound,
  setSecondsLeft,
  ending,
}: AIInterviewerPanelProps) {
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Typewriter reveal for the interviewer's latest line (candidate feedback,
  // 2026-09-03: replies "pop in" all at once after the wait, which reads as
  // abrupt rather than conversational - a real person's reply arrives as
  // words, not a block of text). Resuming a round (page load with existing
  // history) shows that turn instantly instead of replaying it - captured
  // once via a lazy useState initializer (the sanctioned one-time-computation
  // pattern; a ref read/write during render or a synchronous setState in an
  // effect are both flagged by this project's stricter react-hooks rules).
  // Any turn whose index doesn't match what was already there at mount is a
  // turn that arrived during this page's lifetime, so it gets the typewriter
  // - including a round's very first opening line when starting fresh
  // (nothing was there at mount, so nothing can match).
  const [initialInterviewerTurnIndex] = useState<number | null>(
    () => [...transcript].reverse().find((t) => t.speaker === "interviewer")?.turn_index ?? null
  );
  const latestInterviewerTurn = [...transcript].reverse().find((t) => t.speaker === "interviewer");
  const isFirstRevealThisMount = latestInterviewerTurn?.turn_index === initialInterviewerTurnIndex;

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = messageText.trim();
    if (!text || sending) return;

    setSending(true);
    setError(null);
    const candidateTurn: Turn = {
      speaker: "candidate",
      text,
      phase: round.phase,
      turn_index: transcript.length,
    };
    setTranscript((prev) => [...prev, candidateTurn]);
    setMessageText("");

    try {
      const resp = await sendMessage(round.id, text);
      setTranscript((prev) => [...prev, resp.turn]);
      setRound(resp.round);
      setSecondsLeft(resp.round.time_remaining_sec);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Message failed to send");
    } finally {
      setSending(false);
    }
  }

  // Text mode has no mic, so only "thinking" (awaiting a reply) vs "ready"
  // apply here - "listening"/"speaking" are voice-only states, rendered by
  // VoiceControls' own VoiceSessionPanel instead (real LiveKit agent state).
  const presenceState = sending ? "thinking" : "ready";

  // Pure Voice mode (candidate feedback, 2026-09-03): the chat-style
  // transcript panel and text reply form used to render identically to text
  // mode even when there was no text channel to use - showing the AI's TTS
  // output and the candidate's own STT transcript as live chat bubbles
  // undermined the "real phone call" feel, and the always-visible textarea
  // invited typing that voice-only rounds were never meant to support.
  // "Both" mode is untouched below - it deliberately keeps text visible
  // alongside voice. VoiceControls itself still receives every finalized STT/
  // TTS segment via setTranscript (unchanged) - it's just not rendered here.
  if (round.modality === "voice") {
    // Candidate feedback round 2 (2026-09-03): the first pass over-corrected
    // - dropping the live transcript also dropped the *current question*,
    // leaving candidates with nothing to reference while speaking. This box
    // is the fix: it always shows the latest interviewer turn (updated as
    // new voice turns land via VoiceControls' setTranscript), so there's a
    // real "problem statement" on screen the whole round - just not the
    // full multi-turn back-and-forth or the candidate's own STT transcript.
    // flex-1 + justify-center here is deliberate too: this panel is a CSS
    // grid stretch-sibling of the (tall) canvas/coding panel next to it, so
    // without something claiming the extra height it renders as a small
    // card floating above a large empty gap - the exact "left side too much
    // space unused" complaint. Growing this card to fill that height and
    // centering its content uses the space instead of wasting it.
    return (
      <div className="flex flex-col gap-4">
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-lg border border-border bg-surface px-8 py-10 text-center">
          <p className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            Current question
          </p>
          {latestInterviewerTurn ? (
            <p className="max-w-lg whitespace-pre-wrap text-lg leading-relaxed text-foreground">
              {latestInterviewerTurn.text}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {sending ? `${INTERVIEWER_NAME} is thinking...` : `Waiting for ${INTERVIEWER_NAME} to start the conversation...`}
            </p>
          )}
          <p className="max-w-sm text-xs text-muted-foreground">
            Voice-only round - your spoken conversation isn&apos;t shown as text. This box updates with each new
            question as {INTERVIEWER_NAME} responds; speak naturally and use the controls below to mute or end
            the call.
          </p>
        </div>
        <VoiceControls
          roundId={round.id}
          modality={round.modality}
          round={round}
          setTranscript={setTranscript}
          presenceSize="md"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="rounded-lg border border-border bg-surface p-6">
        <AIInterviewerPresence state={presenceState} />

        {latestInterviewerTurn && (
          <p className="mt-5 whitespace-pre-wrap text-base leading-relaxed text-foreground">
            <TypewriterText
              key={latestInterviewerTurn.turn_index}
              text={latestInterviewerTurn.text}
              instant={isFirstRevealThisMount}
            />
          </p>
        )}
        {sending && !latestInterviewerTurn && <p className="mt-5 text-sm text-muted-foreground">Thinking...</p>}

        {transcript.length > 0 && (
          <details open className="mt-5 border-t border-border pt-4">
            <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Full transcript
            </summary>
            <div className="mt-3 space-y-4">
              {transcript.map((turn, i) => (
                <div key={i}>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {turn.speaker === "interviewer" ? "Interviewer" : "You"}
                  </p>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{turn.text}</p>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          </details>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-status-strong-concern">{error}</p>}

      <form onSubmit={handleSend} className="mt-4 flex gap-2">
        <textarea
          value={messageText}
          onChange={(e) => setMessageText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend(e);
            }
          }}
          rows={3}
          placeholder="Type your response..."
          disabled={sending || ending}
          className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={sending || ending || !messageText.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          Send
        </button>
      </form>

      <VoiceControls roundId={round.id} modality={round.modality} round={round} setTranscript={setTranscript} />
    </div>
  );
}


// Reveals `text` in capped steps rather than a fixed per-character delay, so
// a long System Design answer and a short one-liner both finish in roughly
// the same short amount of time instead of the longest replies feeling
// sluggish. `instant` (true only the very first time a page load already has
// history to show) skips the animation entirely. Remounted per turn by the
// caller's `key` so this useState can initialize directly from `instant`
// instead of resetting it via an effect.
function TypewriterText({ text, instant }: { text: string; instant: boolean }) {
  const [shownChars, setShownChars] = useState(instant ? text.length : 0);

  useEffect(() => {
    if (instant) return;
    let shown = 0;
    const stepSize = Math.max(1, Math.ceil(text.length / 90));
    const id = setInterval(() => {
      shown += stepSize;
      setShownChars(Math.min(shown, text.length));
      if (shown >= text.length) {
        clearInterval(id);
      }
    }, 16);
    return () => clearInterval(id);
    // Runs once per mount (this component is remounted per turn via `key`) -
    // text/instant are fixed for this component's whole lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <>{text.slice(0, shownChars)}</>;
}
