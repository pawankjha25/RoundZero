# Milestone 4 - Make It Feel Like A Real Interview

## Status
Draft - the decisions below need your call.

## Scope
LiveKit -> Streaming STT -> Interviewer Agent -> Streaming TTS -> natural voice interview.
Corresponds to tasks.md item 17. Only starts once Milestones 1-3 work in text (PRD section
37 ticket 14). Text fallback stays available always (PRD section 24) - this milestone adds
a transport, it does not replace the text path.

## Why this milestone is mostly a transport swap, not a rewrite

Because the Milestone 1 orchestrator was built against an abstract turn loop
(conversation_state, SessionEvents, interviewer input/output contracts from PRD section
21.1/21.2) rather than literally "a chat text box," the interviewer agent itself does not
need to change here. Voice mode swaps how a turn's input arrives (streaming STT instead of
a typed message) and how the interviewer's utterance is delivered (streaming TTS instead of
rendered text) around the same core loop. If this milestone turns out to require touching
the interviewer/evaluation logic, that's a signal the Milestone 1 abstraction leaked and is
worth revisiting - it should not need to.

## Runtime flow

1. Candidate chooses voice mode (see Decision 1 on default vs opt-in). Check-in also issues
   LiveKit room credentials.
2. Candidate speaks; streaming STT produces partial and final transcripts. Partial
   transcripts can be shown live so the candidate sees their own words appear.
3. Final transcript segments feed the same orchestrator turn loop from Milestone 1,
   unchanged.
4. Interviewer utterance is synthesized via streaming TTS and played to the candidate.
5. TTS is cancellable - if the candidate starts speaking again before playback finishes,
   playback stops (barge-in / interruption handling, PRD section 24).
6. Final transcript is persisted separately from raw audio (PRD section 24). Audio
   retention is configurable and disclosed to the candidate (see Decision 2).
7. Realtime degradation (dropped connection, STT/TTS failure) fails gracefully back to text
   rather than losing the interview (PRD section 24) - this is also where Milestone 1's
   minimal reconnect gets upgraded to real-time/graceful handling.

## Build checklist (dependency order)

- src/roundzero/realtime/session.py, livekit/, stt/, tts/ - none of this exists yet; it was
  deliberately left unscaffolded in the initial folder structure until a milestone actually
  needed it
- Realtime Gateway connecting LiveKit room events into the existing orchestrator turn loop
- Interruption/barge-in handling (TTS cancellation on candidate speech start)
- Audio retention policy + candidate-facing disclosure (PRD section 24, section 25
  privacy-by-default)
- Reconnect upgraded from Milestone 1's event-log-replay-on-reload to real-time graceful
  reconnect
- Frontend: voice UI (mic control, live partial-transcript display, audio playback),
  text/voice mode toggle

## Decisions

1. **Voice as default vs opt-in toggle.** Recommend: opt-in toggle, not the default entry
   point, at least until voice latency/quality is proven in real use. Consistent with PRD
   section 24's "realtime degradation should fail gracefully to text" - don't route
   everyone through the less-proven path by default before you trust it.
2. **Audio retention default.** PRD section 24 says retention should be configurable and
   disclosed, but doesn't set a default. Recommend: default to NOT retaining raw audio
   (delete once the final transcript is confirmed), candidate opts in to keep it -
   consistent with "private by default" being the overriding principle everywhere else in
   the PRD (section 25).
3. **STT/TTS provider.** Not yet chosen - carries forward the same provider-abstraction
   principle as the LLM Gateway (pluggable adapters, no hard-coded vendor). Fine to decide
   at build time, not now.
