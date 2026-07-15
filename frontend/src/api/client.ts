export type GameMode = "4p" | "3p";
export type AccessRole = "guest" | "admin";

export interface AccessResponse {
  role: AccessRole;
}

export interface RemotePlayer {
  source: string;
  externalId: string;
  nickname: string;
  mode: GameMode;
  levelId?: number | null;
  latestTimestamp?: number | null;
}

export interface RemoteGame {
  source: string;
  externalId: string;
  uuid: string;
  mode: GameMode;
  modeId?: number | null;
  startedAt?: number | null;
  endedAt?: number | null;
  players: Array<Record<string, unknown>>;
  scores: number[];
  ranks: number[];
  gradingScores: number[];
}

export interface GamePage {
  games: RemoteGame[];
  nextCursor?: number | null;
}

export interface EventLuckDetail {
  sequence: number;
  player: number;
  component: string;
  actual: number;
  expected: number;
  delta: number;
  variance: number;
  zScore: number;
  includedInTotal: boolean;
  tile?: string | null;
  explanationKey: string;
  features: Record<string, number | string | boolean>;
}

export interface RoundPlayerLuck {
  seat: number;
  rawDelta: number;
  variance: number;
  zScore: number;
  score: number;
  confidence: "low" | "medium" | "high";
  actualPoints: number;
}

export interface RoundLuckAnalysis {
  roundIndex: number;
  label: string;
  players: RoundPlayerLuck[];
  events: EventLuckDetail[];
}

export interface PlayerLuckAnalysis extends RoundPlayerLuck {
  name: string;
  actualPoints: number;
  components: Record<string, number>;
}

export interface GameLuckAnalysis {
  analysisSchemaVersion: string;
  gameHash: string;
  algorithmId: string;
  algorithmVersion: string;
  options: { eventDetails: boolean };
  players: PlayerLuckAnalysis[];
  rounds: RoundLuckAnalysis[];
}

export interface AnalysisEnvelope {
  id: string;
  gameId: string;
  status: string;
  createdAt: string;
  game: AnalysisGameSummary;
  result?: GameLuckAnalysis | null;
  errorCode?: string | null;
}

export interface AnalysisGamePlayer {
  seat: number;
  name: string;
}

export interface AnalysisGameSummary {
  id: string;
  mode: GameMode;
  source: string;
  externalId: string;
  replayUrl?: string | null;
  players: AnalysisGamePlayer[];
  finalScores: number[];
  finalRanks: number[];
}

export interface AlgorithmDescription {
  id: string;
  version: string;
  nameKey: string;
  descriptionKey: string;
  supports: GameMode[];
}

export interface ReplayImportResult {
  replayId: string;
  gameId?: string;
  parseErrorCode?: string;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public parameters: Record<string, unknown> = {},
  ) {
    super(message);
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    return new ApiError(
      typeof body.code === "string" ? body.code : "REQUEST_FAILED",
      typeof body.message === "string" ? body.message : response.statusText,
      response.status,
      typeof body.parameters === "object" && body.parameters ? body.parameters as Record<string, unknown> : {},
    );
  }
}

async function jsonRequest<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) throw await ApiError.fromResponse(response);
  return await response.json() as T;
}

export async function searchPlayers(query: string, mode: GameMode, signal?: AbortSignal): Promise<RemotePlayer[]> {
  const params = new URLSearchParams({ source: "amae-koromo", q: query, mode });
  return jsonRequest<RemotePlayer[]>(`/api/players/search?${params}`, { signal });
}

export async function listPlayerGames(
  player: RemotePlayer,
  cursor?: number,
  signal?: AbortSignal,
): Promise<GamePage> {
  const params = new URLSearchParams({ mode: player.mode });
  if (cursor !== undefined) params.set("cursor", String(cursor));
  return jsonRequest<GamePage>(
    `/api/players/${encodeURIComponent(player.source)}/${encodeURIComponent(player.externalId)}/games?${params}`,
    { signal },
  );
}

export async function importReplayFile(file: File): Promise<ReplayImportResult> {
  const form = new FormData();
  form.append("file", file);
  return jsonRequest("/api/replays/import-file", { method: "POST", body: form });
}

export async function importReplayLocator(locator: string): Promise<ReplayImportResult> {
  return jsonRequest("/api/replays/import-locator", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locator }),
  });
}

export async function listAlgorithms(): Promise<AlgorithmDescription[]> {
  return jsonRequest("/api/algorithms");
}

export async function createAnalysis(gameId: string, algorithmId = "baseline-v1"): Promise<AnalysisEnvelope> {
  return jsonRequest("/api/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gameId, algorithmId, options: { eventDetails: true } }),
  });
}

export async function getAnalysis(id: string, signal?: AbortSignal): Promise<AnalysisEnvelope> {
  return jsonRequest(`/api/results/${id}`, { signal });
}

export async function listAnalyses(signal?: AbortSignal): Promise<AnalysisEnvelope[]> {
  return jsonRequest("/api/analyses", { signal });
}

export async function getAccessRole(signal?: AbortSignal): Promise<AccessResponse> {
  return jsonRequest("/api/access", { signal });
}

export async function createAdminSession(secret: string): Promise<AccessResponse> {
  return jsonRequest("/api/admin/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret }),
  });
}

export async function deleteAdminSession(): Promise<AccessResponse> {
  return jsonRequest("/api/admin/session", { method: "DELETE" });
}
