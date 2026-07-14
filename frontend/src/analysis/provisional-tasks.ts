import type { AnalysisGamePlayer, GameMode, RemoteGame } from "../api/client";


export const PROVISIONAL_ANALYSES_KEY = "haiun.provisionalAnalyses";
export const PROVISIONAL_ANALYSES_EVENT = "haiun:provisional-analyses";

export interface ProvisionalGameSummary {
  mode?: GameMode;
  source?: string;
  externalId?: string;
  players?: AnalysisGamePlayer[];
  finalScores?: number[];
  finalRanks?: number[];
}

export interface ProvisionalAnalysisTask {
  id: string;
  status: "loading_replay" | "failed" | "resolved";
  createdAt: string;
  game: ProvisionalGameSummary;
  analysisId?: string;
}

function notify(): void {
  window.dispatchEvent(new Event(PROVISIONAL_ANALYSES_EVENT));
}

function readAll(): ProvisionalAnalysisTask[] {
  try {
    const value = JSON.parse(localStorage.getItem(PROVISIONAL_ANALYSES_KEY) ?? "[]") as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is ProvisionalAnalysisTask => (
      typeof item === "object" && item !== null
      && typeof (item as ProvisionalAnalysisTask).id === "string"
      && ["loading_replay", "failed", "resolved"].includes((item as ProvisionalAnalysisTask).status)
    ));
  } catch {
    return [];
  }
}

export function listProvisionalAnalyses(): ProvisionalAnalysisTask[] {
  return readAll().filter((task) => task.status !== "resolved");
}

function write(tasks: ProvisionalAnalysisTask[]): void {
  localStorage.setItem(PROVISIONAL_ANALYSES_KEY, JSON.stringify(tasks));
  notify();
}

export function createProvisionalAnalysis(game: ProvisionalGameSummary = {}): ProvisionalAnalysisTask {
  const randomId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const task: ProvisionalAnalysisTask = {
    id: `provisional-${randomId}`,
    status: "loading_replay",
    createdAt: new Date().toISOString(),
    game,
  };
  write([task, ...readAll().filter((item) => item.status !== "resolved")]);
  return task;
}

export function provisionalGameFromRemote(game: RemoteGame): ProvisionalGameSummary {
  return {
    mode: game.mode,
    source: game.source,
    externalId: game.externalId,
    players: game.players.map((player, seat) => ({ seat, name: String(player.nickname ?? "—") })),
    finalScores: game.scores,
    finalRanks: game.ranks,
  };
}

export function getProvisionalAnalysis(id: string): ProvisionalAnalysisTask | null {
  return readAll().find((task) => task.id === id) ?? null;
}

export function failProvisionalAnalysis(id?: string): void {
  if (!id) return;
  write(readAll().map((task) => task.id === id ? { ...task, status: "failed" } : task));
}

export function resolveProvisionalAnalysis(id: string | undefined, analysisId: string): void {
  if (!id) return;
  write(readAll().map((task) => task.id === id ? { ...task, status: "resolved", analysisId } : task));
}

export function removeProvisionalAnalysis(id?: string): void {
  if (!id) return;
  write(readAll().filter((task) => task.id !== id));
}
