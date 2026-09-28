"use client";

// Thin data/state owner: same me()/getRound()/timer-interval/handleSend/
// handleEnd logic as before this refactor, now rendering <InterviewRoom/>
// instead of inline JSX. Same URL, same API calls, same behavior for
// ml_system_design text rounds - the chat loop itself moved into
// AIInterviewerPanel (components/interview/), this page just owns the state
// every workspace type needs (round, transcript, timer).
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import InterviewRoom from "@/components/interview/InterviewRoom";
import { getRound, me, submitRound, type RoundSummary, type Turn } from "@/lib/api";

const ACTIVE_STATUSES = new Set(["ACTIVE", "WRAP_UP"]);

export default function InterviewPage() {
  const router = useRouter();
  const params = useParams<{ roundId: string }>();
  const roundId = params.roundId;

  const [round, setRound] = useState<RoundSummary | null>(null);
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const autoEndedRef = useRef(false);

  // Auth guard only - the interview room's Focus Mode has no app nav to show
  // a signed-in user against (specs/003-premium-uiux-redesign section 8), so
  // nothing here needs the resolved user, just the redirect-if-signed-out.
  useEffect(() => {
    me().catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!roundId) return;
    getRound(roundId)
      .then((detail) => {
        if (!ACTIVE_STATUSES.has(detail.round.status)) {
          router.replace(`/reports/${roundId}`);
          return;
        }
        setRound(detail.round);
        setTranscript(detail.transcript);
        setSecondsLeft(detail.round.time_remaining_sec);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load interview"));
  }, [roundId, router]);

  useEffect(() => {
    const id = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (secondsLeft === 0 && round && ACTIVE_STATUSES.has(round.status) && !autoEndedRef.current && !ending) {
      autoEndedRef.current = true;
      handleEnd();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secondsLeft, round]);

  async function handleEnd() {
    if (!round) return;
    // ending stays true through a failed attempt too - EndInterviewTransition
    // renders its own Retry Evaluation state off endError rather than kicking
    // the candidate back to the (now-stale) workspace view.
    setEnding(true);
    setEndError(null);
    try {
      await submitRound(round.id);
      router.push(`/reports/${round.id}`);
    } catch (err) {
      setEndError(
        err instanceof Error
          ? err.message
          : "Scoring this round hit a temporary error - please try again in a moment."
      );
    }
  }

  if (!round) {
    return null;
  }

  return (
    <>
      {error && (
        <p className="border-b border-status-strong-concern/30 bg-status-strong-concern-bg px-5 py-2 text-center text-sm text-status-strong-concern">
          {error}
        </p>
      )}
      <InterviewRoom
        round={round}
        transcript={transcript}
        setTranscript={setTranscript}
        setRound={setRound}
        secondsLeft={secondsLeft}
        setSecondsLeft={setSecondsLeft}
        ending={ending}
        endError={endError}
        onEnd={handleEnd}
      />
    </>
  );
}
