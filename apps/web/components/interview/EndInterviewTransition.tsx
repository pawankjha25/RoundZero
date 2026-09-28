"use client";

// End-Interview transition screen (specs/003-premium-uiux-redesign Phase 4,
// section 13 "End Interview Experience") - replaces the workspace the moment
// the candidate ends the round, instead of leaving the old workspace sitting
// there with just a button label change ("End Round" -> "Ending...") while
// apps/api/orchestrator.py::submit_round runs its (genuinely real, ~seconds-
// long) scoring + report-synthesis pipeline.
//
// Deliberately two stages, not the five the source doc sketches
// ("transcript processed / evidence extracted / evaluating competencies /
// calibrating level / preparing committee packet") - this repo has no
// server-sent progress events, so a client can only ever honestly know two
// things: the transcript was received (true the instant Submit was clicked)
// and evaluation is in flight (true for the whole request). Inventing finer-
// grained stages we can't actually observe completing would be exactly the
// kind of fabricated progress specs/003 section 29 rules out ("never a
// faked progress percentage") - level calibration and a committee packet
// also don't exist yet (blocked on spec 002's P0.4/P0.6), so listing them
// as steps would promise stages that never run today.
//
// Error copy matches the source doc's section 30 example verbatim ("Your
// interview was saved successfully. Evaluation could not be completed yet.
// [ Retry Evaluation ]") - never shows an invented fallback score.
import AIProcessState from "@/components/ui/AIProcessState";
import Button from "@/components/ui/Button";

export default function EndInterviewTransition({
  error,
  onRetry,
}: {
  error: string | null;
  onRetry: () => void;
}) {
  if (error) {
    return (
      <div className="mx-auto max-w-md py-24 text-center">
        <p className="text-sm font-medium text-foreground">Your interview was saved successfully.</p>
        <p className="mt-1 text-sm text-muted-foreground">Evaluation could not be completed yet. {error}</p>
        <Button onClick={onRetry} className="mt-5">
          Retry Evaluation
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md py-24">
      <AIProcessState
        title="Wrapping up your round"
        steps={[
          { label: "Transcript received", status: "done" },
          { label: "Evaluating your interview", status: "active" },
        ]}
      />
      <p className="mt-4 text-center text-xs text-muted-foreground">
        This can take up to a minute or so. Your transcript, code, and whiteboard are already saved.
      </p>
    </div>
  );
}
