// Thin fetch wrapper around the Round Zero API (apps/api). Auth is Supabase
// (Google OAuth + email magic link, see app/(auth)/login/page.tsx) - the
// backend never sees a password or issues its own session, it verifies the
// Supabase access token on every request (apps/api/deps.py). Round
// setup/interview/report/history endpoints (Milestones 1-3) - see
// specs/001-ml-system-design-vertical-slice/milestone-{1,2,3}.md and
// apps/api/schemas.py, which these types mirror field-for-field.
import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface User {
  id: string;
  email: string;
  name: string;
  is_admin: boolean;
}

async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  // 204 No Content (every DELETE endpoint - admin options/durations/study
  // resources, and now loops) has no body at all; calling res.json() on it
  // throws "Unexpected end of JSON input" instead of resolving, which every
  // apiFetch<void>(..., {method:"DELETE"}) caller was silently exposed to as
  // a real error. Treat "no body" as a valid void response instead of
  // guessing from status code alone, since some 200s (e.g. logout) also have
  // no JSON body worth parsing.
  const raw = await res.text();
  if (!raw) {
    return undefined as T;
  }
  return JSON.parse(raw) as T;
}

// --- Auth ---
// No login() here anymore - the login page calls supabase.auth.signInWithOAuth
// / signInWithOtp directly (app/(auth)/login/page.tsx), since that's a
// Supabase SDK call, not a Round Zero API endpoint.

export function me(): Promise<User> {
  return apiFetch<User>("/v1/auth/me");
}

export async function logout(): Promise<{ ok: boolean }> {
  const supabase = createClient();
  await supabase.auth.signOut();
  return { ok: true };
}

// --- Config ---

export interface OptionItem {
  value: string;
  label: string;
}

export interface CompanyOptionItem {
  value: string;
  label: string;
  tier: string | null;
}

export interface RoundTypeOption {
  value: string;
  label: string;
  enabled: boolean;
}

export interface Options {
  role_families: OptionItem[];
  levels: OptionItem[];
  domains: OptionItem[];
  companies: CompanyOptionItem[];
  duration_minutes: number[];
  round_types: RoundTypeOption[];
}

export function getOptions(): Promise<Options> {
  return apiFetch<Options>("/v1/config/options");
}

// --- Rounds (Milestone 1-3) ---

export type RoundModality = "text" | "voice" | "both";

export interface StartRoundRequest {
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  mode: RoundModality;
  // Defaults server-side to ml_system_design when omitted - only Setup's
  // Coding entry point (?type=coding) sends this today.
  round_type?: string;
}

export interface Turn {
  speaker: "interviewer" | "candidate";
  text: string;
  phase: string;
  turn_index: number;
  // Optional because a few call sites synthesize a Turn locally before the
  // server round-trip confirms it - an optimistic candidate-message bubble
  // (AIInterviewerPanel), a live voice transcription segment (VoiceControls),
  // and the offline dev harness (app/dev/workspaces) - none of those have a
  // real server timestamp yet. Every Turn that actually came from the API
  // (GET .../rounds/{id}, POST .../message) always has one.
  created_at?: string;
}

// Interview Replay (GET /v1/rounds/{id}/timeline) - a chronological merge of
// transcript turns and workspace events (code/test/canvas activity). `kind`
// is "turn:interviewer" | "turn:candidate" for a chat turn, or one of
// "code_change" | "run_attempt" | "test_result" | "canvas_change" for a
// workspace event - `text` is always ready to render as-is (the raw turn
// text, or a short server-built summary for a workspace event; see
// orchestrator._workspace_event_summary - WorkspaceEvent never stores a full
// code/canvas snapshot, only light metadata, so this is honestly a summary,
// not a diff).
export interface TimelineEvent {
  kind: string;
  text: string;
  phase: string | null;
  created_at: string;
}

// Structured scenario data beyond the plain prompt string - populated for
// coding rounds (title/constraints/entry_point/starter code/test cases, see
// apps/api/models.py's RoundAttempt.scenario_meta docstring), {} for
// ml_system_design. test_cases matches TestCaseSpec below field-for-field so
// it can be passed straight into runCode() with no reshaping.
export interface ScenarioMeta {
  title?: string;
  constraints?: string[];
  entry_point?: string;
  starter_code_python?: string;
  test_cases?: TestCaseSpec[];
}

export interface RoundSummary {
  id: string;
  loop_attempt_id: string;
  round_type: string;
  modality: RoundModality;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  status: string;
  phase: string;
  coverage: Record<string, string>;
  time_remaining_sec: number;
  created_at: string;
  submitted_at: string | null;
  scenario_prompt: string;
  scenario_meta: ScenarioMeta;
}

export interface RoundDetail {
  round: RoundSummary;
  transcript: Turn[];
}

export interface MessageResponse {
  round: RoundSummary;
  turn: Turn;
}

export function startRound(req: StartRoundRequest): Promise<RoundDetail> {
  return apiFetch<RoundDetail>("/v1/rounds", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getRound(roundId: string): Promise<RoundDetail> {
  return apiFetch<RoundDetail>(`/v1/rounds/${roundId}`);
}

export function getRoundTimeline(roundId: string): Promise<TimelineEvent[]> {
  return apiFetch<TimelineEvent[]>(`/v1/rounds/${roundId}/timeline`);
}

export function sendMessage(roundId: string, text: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/v1/rounds/${roundId}/message`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function submitRound(roundId: string): Promise<RoundEvaluation> {
  return apiFetch<RoundEvaluation>(`/v1/rounds/${roundId}/submit`, { method: "POST" });
}

export function getReport(roundId: string): Promise<RoundEvaluation> {
  return apiFetch<RoundEvaluation>(`/v1/rounds/${roundId}/report`);
}

export interface VoiceToken {
  url: string;
  token: string;
  room: string;
}

// 409 if the round was started as text-only, 503 if LiveKit/Deepgram aren't
// configured server-side - both are thrown as a plain Error by apiFetch's
// !res.ok handling, so VoiceControls can catch either as "voice unavailable,
// continue by text" per the milestone-4 spec's graceful-degradation rule.
export function getVoiceToken(roundId: string): Promise<VoiceToken> {
  return apiFetch<VoiceToken>(`/v1/rounds/${roundId}/voice/token`);
}

export interface HistoryItem {
  id: string;
  loop_attempt_id: string;
  round_type: string;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  status: string;
  readiness_pct: number | null;
  hire_signal: string | null;
  created_at: string;
  submitted_at: string | null;
}

export function listHistory(): Promise<HistoryItem[]> {
  return apiFetch<HistoryItem[]>("/v1/rounds");
}

// --- Loops (specs/002-full-loop-platform P0.1 Loop Planner) ---
// A loop is created with a name + one or more planned rounds all at once
// (POST /v1/loops) - every round type is selectable, but only ones with a
// real interviewer (`startable: true`, today just ml_system_design) can
// actually be started (POST .../start). Everything else sits in the loop as
// a visible, honestly-labeled "not available yet" entry - same pattern the
// old /loop-planner preview already used, now backed by a real loop.

export interface PlannedRound {
  id: string;
  round_type: string;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  modality: RoundModality;
  sort_order: number;
  startable: boolean;
  started: HistoryItem | null;
}

export interface Loop {
  id: string;
  name: string;
  created_at: string;
  rounds: PlannedRound[];
}

export interface PlannedRoundInput {
  round_type: string;
  duration_minutes: number;
}

export interface LoopCreateRequest {
  name: string;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  mode: RoundModality;
  rounds: PlannedRoundInput[];
}

export function createLoop(payload: LoopCreateRequest): Promise<Loop> {
  return apiFetch<Loop>("/v1/loops", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listLoops(): Promise<Loop[]> {
  return apiFetch<Loop[]>("/v1/loops");
}

export function getLoop(loopId: string): Promise<Loop> {
  return apiFetch<Loop>(`/v1/loops/${loopId}`);
}

// Pre-filled starting point for the loop builder's free-text name field
// (still fully editable, never applied without the person seeing it first) -
// same "Loop-{Company} - {Level Role}-MMDDYY-N" pattern Practice rounds use,
// counted separately so the two never collide with each other.
export function suggestLoopName(params: { role_family: string; level: string; company_profile: string }): Promise<{ name: string }> {
  const qs = new URLSearchParams(params).toString();
  return apiFetch<{ name: string }>(`/v1/loops/suggested-name?${qs}`);
}

export function startPlannedRound(loopId: string, plannedRoundId: string): Promise<RoundDetail> {
  return apiFetch<RoundDetail>(`/v1/loops/${loopId}/rounds/${plannedRoundId}/start`, {
    method: "POST",
  });
}

export function deleteLoop(loopId: string): Promise<void> {
  return apiFetch<void>(`/v1/loops/${loopId}`, { method: "DELETE" });
}

// --- Virtual Hiring Committee synthesis (specs/002-full-loop-platform P0.6) ---
// Only meaningful once a loop has 2+ evaluated real rounds - getLoopCommittee
// is read-only (never triggers the LLM call, 404s if not ready/stale) and
// generateLoopCommittee builds-or-returns-cached-fresh, same two-step
// GET/POST pattern getReport/submitRound already use for a single round's
// report.

export interface CommitteeReport {
  overall_readiness_pct: number;
  overall_hire_signal: string;
  confidence: string;
  headline: string;
  strengths: string[];
  concerns: string[];
  level_signal: string;
  key_evidence: string[];
  rounds_included: string[];
  generated_at: string;
}

export function getLoopCommittee(loopId: string): Promise<CommitteeReport> {
  return apiFetch<CommitteeReport>(`/v1/loops/${loopId}/committee`);
}

export function generateLoopCommittee(loopId: string): Promise<CommitteeReport> {
  return apiFetch<CommitteeReport>(`/v1/loops/${loopId}/committee`, { method: "POST" });
}

// --- Retry / attempt comparison (tasks.md P1 item 16) ---

export interface DimensionScoreDelta {
  dimension: string;
  label: string;
  score_older: number;
  score_newer: number;
  delta: number;
}

export interface RoundComparison {
  round_older: HistoryItem;
  round_newer: HistoryItem;
  evaluation_older: RoundEvaluation;
  evaluation_newer: RoundEvaluation;
  readiness_delta: number;
  hire_signal_older: string;
  hire_signal_newer: string;
  dimension_deltas: DimensionScoreDelta[];
}

export function compareRounds(roundIdA: string, roundIdB: string): Promise<RoundComparison> {
  const params = new URLSearchParams({ round_id_a: roundIdA, round_id_b: roundIdB });
  return apiFetch<RoundComparison>(`/v1/rounds/compare?${params.toString()}`);
}

// --- Evaluation / report shapes (roundzero.evaluation.models.RoundEvaluation) ---

export interface EvidenceItem {
  dimension: string;
  text: string;
  source_turn_index: number;
}

export interface DimensionScore {
  dimension: string;
  label: string;
  weight: number;
  score: number;
  evidence_narrative: string;
  evidence: EvidenceItem[];
}

export interface ImprovementItem {
  dimension: string;
  priority: number;
  recommendation: string;
  based_on: string;
}

// --- Workspace (Coding + System Design panels) ---
// Mirrors apps/api/schemas.py's WorkspaceStateOut / CodeSaveRequest /
// CanvasSaveRequest / RunCodeRequest / RunCodeResult field-for-field, same as
// every other interface in this file.

export interface WorkspaceState {
  round_id: string;
  code_language: string | null;
  code_text: string | null;
  canvas_scene: Record<string, unknown>[] | null;
  canvas_summary: string | null;
  updated_at: string | null;
}

export interface TestCaseSpec {
  name: string;
  input?: string | null;
  expected_output?: string | null;
}

export interface TestCaseResult {
  name: string;
  passed: boolean | null;
  actual_output: string | null;
}

export interface CodeQualityFeedback {
  summary: string;
  strengths: string[];
  concerns: string[];
  complexity_note: string | null;
  interviewer_followup: string | null;
}

export interface RunCodeResult {
  stdout: string;
  stderr: string;
  test_results: TestCaseResult[];
  executed: boolean;
  ran_at: string;
  feedback: CodeQualityFeedback | null;
}

export function getWorkspaceState(roundId: string): Promise<WorkspaceState> {
  return apiFetch<WorkspaceState>(`/v1/rounds/${roundId}/workspace`);
}

export function saveCode(roundId: string, codeLanguage: string, codeText: string): Promise<WorkspaceState> {
  return apiFetch<WorkspaceState>(`/v1/rounds/${roundId}/workspace/code`, {
    method: "PUT",
    body: JSON.stringify({ code_language: codeLanguage, code_text: codeText }),
  });
}

export function saveCanvas(
  roundId: string,
  canvasScene: Record<string, unknown>[],
  canvasSummary: string
): Promise<WorkspaceState> {
  return apiFetch<WorkspaceState>(`/v1/rounds/${roundId}/workspace/canvas`, {
    method: "PUT",
    body: JSON.stringify({ canvas_scene: canvasScene, canvas_summary: canvasSummary }),
  });
}

export function runCode(
  roundId: string,
  language: string,
  code: string,
  testCases: TestCaseSpec[] = [],
  entryPoint?: string | null
): Promise<RunCodeResult> {
  return apiFetch<RunCodeResult>(`/v1/rounds/${roundId}/workspace/run`, {
    method: "POST",
    body: JSON.stringify({ language, code, test_cases: testCases, entry_point: entryPoint ?? null }),
  });
}

// specs/002 P0.4 "Level Calibration" - maps the round's own readiness_pct/
// hire_signal (already scored against one fixed Staff/Principal-caliber bar,
// see src/roundzero/leveling/calibration.py's docstring) onto the app's
// senior/staff/principal ladder. Below LEAN HIRE (readiness_pct < 50) all
// three targets are null and the narrative explains why, rather than
// guessing a level from a round that didn't clear the bar.
export interface LevelCalibration {
  safe_target: string | null;
  competitive_target: string | null;
  stretch_target: string | null;
  narrative: string;
}

export interface RoundEvaluation {
  round_id: string;
  dimension_scores: DimensionScore[];
  readiness_pct: number;
  hire_signal: string;
  primary_concern: string;
  strengths: string[];
  weaknesses: string[];
  improvement_plan: ImprovementItem[];
  level_calibration: LevelCalibration;
}

// --- Candidate profile ---
// Who the candidate is and what they're aiming for - separate from any single
// round's Setup choices (role_family/level/domain live on the round itself).
// GET always resolves even before the candidate has ever saved anything (every
// field null), so the profile page never has to special-case a 404.

export interface Profile {
  current_role: string | null;
  target_role: string | null;
  years_experience: number | null;
  experience_summary: string | null;
  objective: string | null;
  linkedin_url: string | null;
  updated_at: string | null;
}

export interface ProfileUpdate {
  current_role: string | null;
  target_role: string | null;
  years_experience: number | null;
  experience_summary: string | null;
  objective: string | null;
  linkedin_url: string | null;
}

export function getProfile(): Promise<Profile> {
  return apiFetch<Profile>("/v1/profile");
}

export function updateProfile(payload: ProfileUpdate): Promise<Profile> {
  return apiFetch<Profile>("/v1/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// --- Report summary (/report) ---
// Mirrors apps/api/routes/report.py's ReportSummaryOut field-for-field.

export interface WeakDimension {
  dimension: string;
  label: string;
  score: number;
}

export interface SuggestedResource {
  id: string;
  dimension: string;
  kind: string;
  title: string;
  url: string | null;
  note: string | null;
}

export interface ReportSummary {
  total_loops: number;
  total_rounds: number;
  evaluated_rounds: number;
  avg_readiness_pct: number | null;
  latest_readiness_pct: number | null;
  latest_hire_signal: string | null;
  weakest_dimensions: WeakDimension[];
  suggested_resources: SuggestedResource[];
  consultancy_url: string | null;
  substack_url: string | null;
  class_url: string | null;
  loops: HistoryItem[];
}

export function getReportSummary(): Promise<ReportSummary> {
  return apiFetch<ReportSummary>("/v1/report/summary");
}

// --- Admin (apps/api/routes/admin.py) - every call here 403s for a
// non-admin, enforced server-side by ADMIN_EMAILS; the frontend only hides
// the nav link, it never relies on that hiding for actual access control. ---

export type AdminOptionKind = "role-families" | "levels" | "domains" | "companies";

export interface AdminOptionRow {
  value: string;
  label: string;
  sort_order: number;
  tier: string | null;
}

export interface AdminOptionRowIn {
  value: string;
  label: string;
  sort_order?: number;
  tier?: string | null;
}

export interface AdminOptionRowUpdate {
  label?: string;
  sort_order?: number;
  tier?: string | null;
}

export function adminListOptions(kind: AdminOptionKind): Promise<AdminOptionRow[]> {
  return apiFetch<AdminOptionRow[]>(`/v1/admin/options/${kind}`);
}

export function adminCreateOption(kind: AdminOptionKind, payload: AdminOptionRowIn): Promise<AdminOptionRow> {
  return apiFetch<AdminOptionRow>(`/v1/admin/options/${kind}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function adminUpdateOption(
  kind: AdminOptionKind,
  value: string,
  payload: AdminOptionRowUpdate
): Promise<AdminOptionRow> {
  return apiFetch<AdminOptionRow>(`/v1/admin/options/${kind}/${encodeURIComponent(value)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function adminDeleteOption(kind: AdminOptionKind, value: string): Promise<void> {
  return apiFetch<void>(`/v1/admin/options/${kind}/${encodeURIComponent(value)}`, { method: "DELETE" });
}

export interface AdminDuration {
  minutes: number;
  sort_order: number;
}

export function adminListDurations(): Promise<AdminDuration[]> {
  return apiFetch<AdminDuration[]>("/v1/admin/durations");
}

export function adminCreateDuration(payload: AdminDuration): Promise<AdminDuration> {
  return apiFetch<AdminDuration>("/v1/admin/durations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function adminDeleteDuration(minutes: number): Promise<void> {
  return apiFetch<void>(`/v1/admin/durations/${minutes}`, { method: "DELETE" });
}

export interface AdminRoundType {
  value: string;
  label: string;
  enabled: boolean;
  sort_order: number;
}

export interface AdminRoundTypeUpdate {
  label?: string;
  enabled?: boolean;
  sort_order?: number;
}

export function adminListRoundTypes(): Promise<AdminRoundType[]> {
  return apiFetch<AdminRoundType[]>("/v1/admin/round-types");
}

export function adminUpdateRoundType(value: string, payload: AdminRoundTypeUpdate): Promise<AdminRoundType> {
  return apiFetch<AdminRoundType>(`/v1/admin/round-types/${encodeURIComponent(value)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export interface AdminStudyResource {
  id: string;
  dimension: string;
  round_type: string;
  kind: string;
  title: string;
  url: string | null;
  note: string | null;
  sort_order: number;
}

export interface AdminStudyResourceIn {
  dimension: string;
  round_type?: string;
  kind?: string;
  title: string;
  url?: string | null;
  note?: string | null;
  sort_order?: number;
}

export interface AdminStudyResourceUpdate {
  dimension?: string;
  kind?: string;
  title?: string;
  url?: string | null;
  note?: string | null;
  sort_order?: number;
}

export function adminListStudyResources(): Promise<AdminStudyResource[]> {
  return apiFetch<AdminStudyResource[]>("/v1/admin/study-resources");
}

export function adminCreateStudyResource(payload: AdminStudyResourceIn): Promise<AdminStudyResource> {
  return apiFetch<AdminStudyResource>("/v1/admin/study-resources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function adminUpdateStudyResource(
  id: string,
  payload: AdminStudyResourceUpdate
): Promise<AdminStudyResource> {
  return apiFetch<AdminStudyResource>(`/v1/admin/study-resources/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function adminDeleteStudyResource(id: string): Promise<void> {
  return apiFetch<void>(`/v1/admin/study-resources/${id}`, { method: "DELETE" });
}

export interface AdminSetting {
  key: string;
  value: string | null;
}

export function adminListSettings(): Promise<AdminSetting[]> {
  return apiFetch<AdminSetting[]>("/v1/admin/settings");
}

export function adminUpdateSetting(key: string, value: string | null): Promise<AdminSetting> {
  return apiFetch<AdminSetting>(`/v1/admin/settings/${key}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
}

// --- Real Interview Experience + Outcome (specs/002-full-loop-platform P0.11/P0.12) ---
// A candidate's own log of interviews they went through at real companies -
// separate from every simulated-round type above. See apps/api/routes/
// real_interviews.py and apps/api/orchestrator.py::real_interview_prediction
// for the "prediction computed live, never stored" design.

export interface RealInterviewRound {
  round_type_label: string;
  question_family: string;
  follow_ups: string;
  difficulty: string;
}

export interface RealInterviewOutcome {
  status: "rejected" | "advanced" | "offer" | "withdrew" | "no_response";
  stage: string | null;
  target_level: string | null;
  offered_level: string | null;
  notes: string | null;
  updated_at: string;
}

export interface RealInterviewPrediction {
  source: "committee" | "round";
  readiness_pct: number;
  hire_signal: string;
}

export interface RealInterviewExperience {
  id: string;
  company: string;
  role_family: string;
  level: string;
  domain: string | null;
  interview_date: string;
  linked_loop_attempt_id: string | null;
  rounds: RealInterviewRound[];
  notes: string | null;
  self_assessment: string | null;
  visibility: "private" | "anonymous" | "community";
  created_at: string;
  updated_at: string;
  outcome: RealInterviewOutcome | null;
  prediction: RealInterviewPrediction | null;
}

export interface RealInterviewExperienceInput {
  company: string;
  role_family: string;
  level: string;
  domain?: string | null;
  interview_date: string;
  linked_loop_attempt_id?: string | null;
  rounds: RealInterviewRound[];
  notes?: string | null;
  self_assessment?: string | null;
  visibility: "private" | "anonymous" | "community";
}

export interface RealInterviewOutcomeInput {
  status: "rejected" | "advanced" | "offer" | "withdrew" | "no_response";
  stage?: string | null;
  target_level?: string | null;
  offered_level?: string | null;
  notes?: string | null;
}

export interface StructuredExperience {
  rounds: RealInterviewRound[];
  self_assessment: string;
}

export function createRealInterview(req: RealInterviewExperienceInput): Promise<RealInterviewExperience> {
  return apiFetch<RealInterviewExperience>("/v1/real-interviews", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function listRealInterviews(): Promise<RealInterviewExperience[]> {
  return apiFetch<RealInterviewExperience[]>("/v1/real-interviews");
}

export function getRealInterview(id: string): Promise<RealInterviewExperience> {
  return apiFetch<RealInterviewExperience>(`/v1/real-interviews/${id}`);
}

export function updateRealInterview(id: string, req: RealInterviewExperienceInput): Promise<RealInterviewExperience> {
  return apiFetch<RealInterviewExperience>(`/v1/real-interviews/${id}`, {
    method: "PATCH",
    body: JSON.stringify(req),
  });
}

export function deleteRealInterview(id: string): Promise<void> {
  return apiFetch<void>(`/v1/real-interviews/${id}`, { method: "DELETE" });
}

export function upsertRealInterviewOutcome(id: string, req: RealInterviewOutcomeInput): Promise<RealInterviewExperience> {
  return apiFetch<RealInterviewExperience>(`/v1/real-interviews/${id}/outcome`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// Preview only - nothing is persisted by this call. The candidate reviews
// and edits the returned draft before createRealInterview/updateRealInterview
// actually saves anything.
export function structureRealInterviewText(rawText: string, hints: string): Promise<StructuredExperience> {
  return apiFetch<StructuredExperience>("/v1/real-interviews/structure", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, hints }),
  });
}

// --- Prep Plans (user-pitched feature, not from the P0 backlog) ---
// A candidate's own self-curated prep plan (e.g. "Staff MLE prep"),
// organized into areas each holding a list of practice questions picked
// deliberately - "what am I in the mood to practice today" - instead of
// always getting a randomly picked scenario. See apps/api/models.py's
// PrepPlan/PrepPlanArea/PrepPlanQuestion docstrings for the full design.

export type PrepPlanQuestionSource = "bank" | "custom" | "ai";

export interface QuestionProgress {
  attempts: number;
  latest_status: string | null;
  latest_readiness_pct: number | null;
  latest_hire_signal: string | null;
}

export interface PrepPlanQuestion {
  id: string;
  area_id: string;
  prompt: string;
  notes: string | null;
  source: PrepPlanQuestionSource;
  scenario_id: string | null;
  progress: QuestionProgress;
}

export interface PrepPlanArea {
  id: string;
  plan_id: string;
  round_type: string;
  label: string;
  sort_order: number;
  questions: PrepPlanQuestion[];
}

export interface PrepPlan {
  id: string;
  name: string;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  mode: RoundModality;
  created_at: string;
  updated_at: string;
  areas: PrepPlanArea[];
}

export interface PrepPlanInput {
  name: string;
  role_family: string;
  level: string;
  domain: string;
  company_profile: string;
  duration_minutes: number;
  mode: RoundModality;
}

export interface BankScenario {
  scenario_id: string;
  prompt: string;
  title: string | null;
}

export interface SuggestedQuestion {
  prompt: string;
  notes: string;
  scenario_id: string | null;
}

export function createPrepPlan(req: PrepPlanInput): Promise<PrepPlan> {
  return apiFetch<PrepPlan>("/v1/prep-plans", { method: "POST", body: JSON.stringify(req) });
}

export function listPrepPlans(): Promise<PrepPlan[]> {
  return apiFetch<PrepPlan[]>("/v1/prep-plans");
}

export function getPrepPlan(id: string): Promise<PrepPlan> {
  return apiFetch<PrepPlan>(`/v1/prep-plans/${id}`);
}

export function deletePrepPlan(id: string): Promise<void> {
  return apiFetch<void>(`/v1/prep-plans/${id}`, { method: "DELETE" });
}

export function addPrepPlanArea(planId: string, roundType: string, label: string): Promise<PrepPlanArea> {
  return apiFetch<PrepPlanArea>(`/v1/prep-plans/${planId}/areas`, {
    method: "POST",
    body: JSON.stringify({ round_type: roundType, label }),
  });
}

export function deletePrepPlanArea(areaId: string): Promise<void> {
  return apiFetch<void>(`/v1/prep-plans/areas/${areaId}`, { method: "DELETE" });
}

export function listBankScenarios(areaId: string): Promise<BankScenario[]> {
  return apiFetch<BankScenario[]>(`/v1/prep-plans/areas/${areaId}/bank-scenarios`);
}

export function addQuestionFromBank(areaId: string, scenarioId: string): Promise<PrepPlanQuestion> {
  return apiFetch<PrepPlanQuestion>(`/v1/prep-plans/areas/${areaId}/questions/from-bank`, {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function addCustomQuestion(areaId: string, prompt: string, notes: string): Promise<PrepPlanQuestion> {
  return apiFetch<PrepPlanQuestion>(`/v1/prep-plans/areas/${areaId}/questions/custom`, {
    method: "POST",
    body: JSON.stringify({ prompt, notes: notes || null }),
  });
}

// Preview only - nothing is persisted by this call. The candidate adds
// whichever suggestions they want individually via addSuggestedQuestion.
export function suggestQuestions(areaId: string): Promise<SuggestedQuestion[]> {
  return apiFetch<{ questions: SuggestedQuestion[] }>(`/v1/prep-plans/areas/${areaId}/suggest-questions`, {
    method: "POST",
  }).then((res) => res.questions);
}

export function addSuggestedQuestion(areaId: string, suggestion: SuggestedQuestion): Promise<PrepPlanQuestion> {
  return apiFetch<PrepPlanQuestion>(`/v1/prep-plans/areas/${areaId}/questions/from-suggestion`, {
    method: "POST",
    body: JSON.stringify(suggestion),
  });
}

export function deletePrepPlanQuestion(questionId: string): Promise<void> {
  return apiFetch<void>(`/v1/prep-plans/questions/${questionId}`, { method: "DELETE" });
}

// Click a question, start a round against exactly that scenario - returns
// the same RoundDetail shape startRound() does, so the caller routes into
// the normal interview room unchanged.
export function startRoundFromQuestion(questionId: string): Promise<RoundDetail> {
  return apiFetch<RoundDetail>(`/v1/prep-plans/questions/${questionId}/start`, { method: "POST" });
}

// "Practice this weakness" (report page) - starts a new round biased toward
// one item from an already-evaluated round's improvement plan (priority
// matches ImprovementItem.priority, 1 = highest). Returns the same
// RoundDetail shape startRound() does, so the caller routes into the normal
// interview room unchanged.
export function startDrill(roundId: string, priority: number): Promise<RoundDetail> {
  return apiFetch<RoundDetail>(`/v1/rounds/${roundId}/drill`, {
    method: "POST",
    body: JSON.stringify({ priority }),
  });
}

// --- Feedback (small-pilot "report an issue/feedback/advice" widget - see
// apps/web/components/FeedbackWidget.tsx, mounted globally in app/layout.tsx
// outside AppShell so it's reachable even mid-interview. Backend: apps/api/
// routes/feedback.py for the POST, apps/api/routes/admin.py for the
// admin-only listing.) ---

export type FeedbackKind = "feedback" | "issue" | "advice";

export interface FeedbackSubmission {
  kind: FeedbackKind;
  message: string;
  page_path?: string | null;
}

export function submitFeedback(payload: FeedbackSubmission): Promise<{ id: string; kind: FeedbackKind }> {
  return apiFetch<{ id: string; kind: FeedbackKind }>("/v1/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface AdminFeedback {
  id: string;
  user_email: string;
  user_name: string;
  kind: FeedbackKind;
  message: string;
  page_path: string | null;
  created_at: string;
}

export function adminListFeedback(): Promise<AdminFeedback[]> {
  return apiFetch<AdminFeedback[]>("/v1/admin/feedback");
}

// --- World-model interviewer (specs/005-world-model-interviewer) ---
// Mirrors src/roundzero/worldmodel/models.py and apps/api/routes/world_model.py.
// Every per-round call only works after the interview is submitted (the level
// read is never shown live - decided 2026-09-28); the API returns 409 before.

export type WMPolarity = "demonstrated" | "absent" | "contradicted";
export type WMNodeStatus = "strong" | "thin" | "wrong" | "none";

export interface WMEvidence {
  turn_index: number;
  dimension: string;
  competency: string | null;
  criterion: string;
  polarity: WMPolarity;
  span: string | null;
  strength: number;
  extractor_version: string;
}

export interface WMPathPoint {
  turn_index: number;
  label: string;
  question: string;
  answer: string;
  level_mean: number;
  level_std: number;
  status: WMNodeStatus;
  evidence: WMEvidence[];
}

export interface WMCause {
  turn_index: number;
  evidence: WMEvidence;
  impact: number;
  explanation: string;
}

export interface WMCompetencyDiagnosis {
  competency: string;
  label: string;
  final_level: string | null;
  final_level_label: string | null;
  final_mean: number;
  confidence: number;
  total_strength: number;
  abstained: boolean;
  abstain_reason: string | null;
  path: WMPathPoint[];
  went_wrong_turn: number | null;
  causes: WMCause[];
}

export interface WMFlipRewrite {
  id: string | null;
  competency: string;
  turn_index: number;
  criterion: string;
  polarity: WMPolarity;
  added_text: string;
  edited_answer: string;
  current_mean: number;
  current_level: string;
  projected_mean: number;
  projected_level: string;
  flipped: boolean;
  rescore_evidence: WMEvidence[];
  writer_version: string;
  scorer_version: string;
  hypothetical: boolean;
}

export interface WMRetryResult {
  id: string | null;
  turn_index: number;
  retry_text: string;
  evidence: WMEvidence[];
  before: Record<string, number>;
  after: Record<string, number>;
  scorer_version: string;
}

export interface WorldModelReport {
  round_id: string;
  round_type: string;
  target_level: string;
  adaptive_mode: string;
  extractor_version: string | null;
  answers_processed: number;
  answers_total: number;
  competencies: WMCompetencyDiagnosis[];
  rewrites: WMFlipRewrite[];
  retries: WMRetryResult[];
  flip_available: boolean;
  decisions_logged: number;
}

export interface CompetencyTrendPoint {
  round_id: string;
  round_type: string;
  created_at: string | null;
  levels: { competency: string; label: string; mean: number; level: string | null; abstained: boolean }[];
}

export function getWorldModel(roundId: string): Promise<WorldModelReport> {
  return apiFetch<WorldModelReport>(`/v1/rounds/${roundId}/world-model`);
}

export function createFlipRewrites(roundId: string): Promise<WMFlipRewrite[]> {
  return apiFetch<WMFlipRewrite[]>(`/v1/rounds/${roundId}/world-model/rewrites`, { method: "POST" });
}

export function createRetry(roundId: string, turnIndex: number, text: string): Promise<WMRetryResult> {
  return apiFetch<WMRetryResult>(`/v1/rounds/${roundId}/world-model/retries`, {
    method: "POST",
    body: JSON.stringify({ turn_index: turnIndex, text }),
  });
}

export function getCompetencyTrend(): Promise<CompetencyTrendPoint[]> {
  return apiFetch<CompetencyTrendPoint[]>("/v1/report/competency-trend");
}
