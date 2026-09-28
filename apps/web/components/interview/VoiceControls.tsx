"use client";

// Real-time voice mode (Milestone 4). Renders nothing for modality "text" -
// only voice/both rounds get a working control here. "Enable voice" mints a
// LiveKit room-join token (apps/api routes/rounds.py voice/token endpoint,
// backed by src/roundzero/realtime/tokens.py) then connects via
// @livekit/components-react's LiveKitRoom, which does the actual WebRTC
// join/mic-publish/audio-playback work. The interview logic itself lives in
// a separate LiveKit Agents worker process (src/roundzero/realtime/agent.py)
// that joins the same room and calls the exact same
// apps.api.orchestrator.post_message() the text path uses - this component
// never talks to the interviewer directly, only to the room.
//
// Finalized STT/TTS transcript segments (published by the agent worker via
// LiveKit's standard transcription text-stream, "lk.transcription_final") are
// pushed into the same `transcript` state the text path's AIInterviewerPanel
// already appends to, reusing the exact Turn shape - no separate rendering
// path needed. A 409 (round started as text-only) or 503 (LiveKit/Deepgram
// not configured) from the token endpoint is shown via ConnectionState
// ("voice unavailable, continue by text") rather than a hard failure, per
// the milestone-4 spec's graceful-degradation rule and
// specs/003-premium-uiux-redesign section 30's error-UX rule (never make a
// candidate feel like their interview state was lost).
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { getVoiceToken, type RoundModality, type RoundSummary, type Turn } from "@/lib/api";
import AIInterviewerPresence, { type PresenceState } from "./AIInterviewerPresence";
import ConnectionState from "@/components/ui/ConnectionState";

interface VoiceControlsProps {
  roundId: string;
  modality: RoundModality;
  round: RoundSummary;
  setTranscript: Dispatch<SetStateAction<Turn[]>>;
  // "md" for pure Voice mode, where this presence indicator is the primary
  // visual element on screen (no transcript panel above it - see
  // AIInterviewerPanel's voice-only branch) and needs to read clearly during
  // the multi-second gap while the interviewer's reply is generated. Default
  // "sm" keeps today's compact inline look for "both"-modality rounds, where
  // it sits underneath a full transcript panel and shouldn't compete with it.
  presenceSize?: "sm" | "md";
}

// LiveKit's standard transcription attribute keys - see
// @livekit/components-core's helper/participant-attributes.ts
// (ParticipantAgentAttributes). Not imported from that package directly to
// avoid an extra dependency beyond what was scoped for this pass; these two
// keys are part of LiveKit's stable wire format, not this component's guess.
const TRANSCRIPTION_FINAL_ATTR = "lk.transcription_final";
const TRANSCRIPTION_SEGMENT_ID_ATTR = "lk.segment_id";

export default function VoiceControls({
  roundId,
  modality,
  round,
  setTranscript,
  presenceSize = "sm",
}: VoiceControlsProps) {
  const [connection, setConnection] = useState<{ url: string; token: string } | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (modality === "text") return null;

  async function handleEnable() {
    setConnecting(true);
    setError(null);
    try {
      const info = await getVoiceToken(roundId);
      setConnection({ url: info.url, token: info.token });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice mode is unavailable right now - continue by text.");
    } finally {
      setConnecting(false);
    }
  }

  if (!connection) {
    if (error) {
      return (
        <div className="mt-3">
          <ConnectionState status="interrupted" onRetry={handleEnable} />
        </div>
      );
    }
    return (
      <div className="mt-3 flex items-center justify-between rounded-md border border-dashed border-border bg-muted px-3 py-2">
        <span className="text-xs text-muted-foreground">Voice mode is available for this round.</span>
        <button
          type="button"
          onClick={handleEnable}
          disabled={connecting}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:border-border-strong disabled:opacity-50"
        >
          {connecting ? "Connecting..." : "Enable voice"}
        </button>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={connection.url}
      token={connection.token}
      audio
      connect
      onDisconnected={() => setConnection(null)}
      onError={(err) => {
        setError(err.message || "Voice call disconnected - continue by text.");
        setConnection(null);
      }}
    >
      <RoomAudioRenderer />
      <VoiceSessionPanel round={round} setTranscript={setTranscript} presenceSize={presenceSize} />
    </LiveKitRoom>
  );
}

function VoiceSessionPanel({
  round,
  setTranscript,
  presenceSize,
}: {
  round: RoundSummary;
  setTranscript: Dispatch<SetStateAction<Turn[]>>;
  presenceSize: "sm" | "md";
}) {
  const { state: agentState } = useVoiceAssistant();
  const transcriptions = useTranscriptions();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const room = useRoomContext();
  const appendedSegments = useRef<Set<string>>(new Set());

  useEffect(() => {
    for (const stream of transcriptions) {
      const isFinal = stream.streamInfo.attributes?.[TRANSCRIPTION_FINAL_ATTR] === "true";
      if (!isFinal) continue;
      const segmentId =
        stream.streamInfo.attributes?.[TRANSCRIPTION_SEGMENT_ID_ATTR] ?? stream.streamInfo.id;
      if (appendedSegments.current.has(segmentId)) continue;
      appendedSegments.current.add(segmentId);

      const speaker: Turn["speaker"] =
        stream.participantInfo.identity === localParticipant.identity ? "candidate" : "interviewer";
      setTranscript((prev) => [
        ...prev,
        { speaker, text: stream.text, phase: round.phase, turn_index: prev.length },
      ]);
    }
  }, [transcriptions, localParticipant.identity, round.phase, setTranscript]);

  const presenceState: PresenceState =
    agentState === "speaking" || agentState === "listening" || agentState === "thinking" ? agentState : "ready";

  return (
    <div
      className={
        "mt-3 flex items-center justify-between rounded-md border border-border bg-surface " +
        (presenceSize === "md" ? "px-4 py-3.5" : "px-3 py-2.5")
      }
    >
      <AIInterviewerPresence state={presenceState} size={presenceSize} />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:border-border-strong"
        >
          {isMicrophoneEnabled ? "Mute" : "Unmute"}
        </button>
        <button
          type="button"
          onClick={() => room.disconnect()}
          className="rounded-md border border-status-strong-concern/40 px-2.5 py-1 text-xs font-medium text-status-strong-concern hover:bg-status-strong-concern-bg"
        >
          End voice
        </button>
      </div>
    </div>
  );
}
