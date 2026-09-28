// Design-system component (specs/003-premium-uiux-redesign section 9 "AI
// Interviewer Presence" + section 36's component list). A subtle
// professional identity - no cartoon avatar, no fake human photo - shared
// between the text path (AIInterviewerPanel, mapped from `sending`) and the
// voice path (VoiceControls, mapped from LiveKit's useVoiceAssistant state).
//
// AVA is a UI-only display name for the interviewer persona, not a backend
// concept - there is no "interviewer identity" field anywhere in the data
// model (round.round_type is what actually drives prompts/rubrics). If a
// named-persona system ever ships (specs/002-full-loop-platform's
// "interviewer personas" admin item), swap this constant for that data.
export const INTERVIEWER_NAME = "Ava";

export type PresenceState = "ready" | "listening" | "thinking" | "speaking";

const STATE_LABEL: Record<PresenceState, string> = {
  ready: "Ready",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

export default function AIInterviewerPresence({
  state,
  size = "md",
}: {
  state: PresenceState;
  size?: "sm" | "md";
}) {
  const orbSize = size === "sm" ? "h-8 w-8" : "h-12 w-12";
  const isLive = state === "listening" || state === "speaking";

  return (
    <div className="flex items-center gap-3">
      <span className="relative flex shrink-0 items-center justify-center">
        {isLive && <span className={`absolute ${orbSize} animate-pulse rounded-full bg-accent/20`} />}
        <span
          className={`relative flex ${orbSize} items-center justify-center rounded-full border ${
            state === "thinking" ? "border-accent/40 bg-accent/10" : "border-border bg-muted"
          }`}
        >
          <span
            className={
              "rounded-full bg-accent transition-opacity " +
              (size === "sm" ? "h-2 w-2" : "h-3 w-3") +
              (state === "thinking" ? " animate-pulse" : "")
            }
          />
        </span>
      </span>
      <div>
        <p className={"font-medium text-foreground " + (size === "sm" ? "text-sm" : "text-base")}>
          {INTERVIEWER_NAME}
        </p>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className={"h-1.5 w-1.5 rounded-full " + (isLive ? "bg-status-positive" : "bg-muted-foreground/50")} />
          {STATE_LABEL[state]}
        </p>
      </div>
    </div>
  );
}
