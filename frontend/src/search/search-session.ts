import type { GameMode, RemotePlayer } from "../api/client";


const PLAYER_SEARCH_KEY = "haiun.playerSearch";
const SELECTED_PLAYER_KEY = "haiun.selectedPlayer";

export interface PlayerSearchSession {
  query: string;
  mode: GameMode;
  players: RemotePlayer[];
  state: "idle" | "done";
}

export function loadPlayerSearchSession(): PlayerSearchSession {
  try {
    const value = JSON.parse(sessionStorage.getItem(PLAYER_SEARCH_KEY) ?? "null") as Partial<PlayerSearchSession> | null;
    if (!value || typeof value.query !== "string" || !Array.isArray(value.players)) throw new Error("invalid");
    return {
      query: value.query,
      mode: value.mode === "3p" ? "3p" : "4p",
      players: value.players,
      state: value.state === "done" ? "done" : "idle",
    };
  } catch {
    return { query: "", mode: "4p", players: [], state: "idle" };
  }
}

export function savePlayerSearchSession(value: PlayerSearchSession): void {
  sessionStorage.setItem(PLAYER_SEARCH_KEY, JSON.stringify(value));
}

export function loadSelectedPlayer(): RemotePlayer | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(SELECTED_PLAYER_KEY) ?? "null") as RemotePlayer | null;
    return value && typeof value.externalId === "string" && typeof value.nickname === "string" ? value : null;
  } catch {
    return null;
  }
}

export function saveSelectedPlayer(player: RemotePlayer | null): void {
  if (player) sessionStorage.setItem(SELECTED_PLAYER_KEY, JSON.stringify(player));
  else sessionStorage.removeItem(SELECTED_PLAYER_KEY);
}
