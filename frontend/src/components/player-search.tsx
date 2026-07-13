import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, type GameMode, type RemotePlayer, searchPlayers } from "../api/client";


export function PlayerSearch({ onSelect }: { onSelect?: (player: RemotePlayer) => void }) {
  const { t } = useTranslation("search");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<GameMode>("4p");
  const [players, setPlayers] = useState<RemotePlayer[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setState("loading");
    try {
      setPlayers(await searchPlayers(query.trim(), mode, new AbortController().signal));
      setState("done");
    } catch (error) {
      setState("error");
      if (!(error instanceof ApiError)) throw error;
    }
  }

  return (
    <section className="work-section" aria-labelledby="player-search-title">
      <div className="section-heading">
        <div>
          <p className="section-index">01</p>
          <h2 id="player-search-title">{t("playerSearch.title")}</h2>
        </div>
        <p>{t("playerSearch.description")}</p>
      </div>
      <div className="mode-switch" aria-label={t("playerSearch.title")}>
        <button className={mode === "4p" ? "is-active" : ""} type="button" onClick={() => setMode("4p")}>
          {t("playerSearch.fourPlayer")}
        </button>
        <button className={mode === "3p" ? "is-active" : ""} type="button" onClick={() => setMode("3p")}>
          {t("playerSearch.threePlayer")}
        </button>
      </div>
      <form className="search-line" onSubmit={(event) => void submit(event)}>
        <label>
          <span>{t("playerSearch.name")}</span>
          <input
            aria-label={t("playerSearch.name")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("playerSearch.placeholder")}
          />
        </label>
        <button className="primary-action" type="submit" disabled={state === "loading"}>
          {state === "loading" ? t("playerSearch.loading") : t("playerSearch.submit")}
        </button>
      </form>
      {state === "error" && <p className="inline-error">{t("replayImport.error")}</p>}
      {state === "done" && players.length === 0 && <p className="empty-state">{t("playerSearch.empty")}</p>}
      {players.length > 0 && (
        <ul className="player-results">
          {players.map((player) => (
            <li key={`${player.mode}-${player.externalId}`}>
              <button type="button" onClick={() => onSelect?.(player)}>
                <span className="seat-stamp">{player.mode === "4p" ? "四" : "三"}</span>
                <span><strong>{player.nickname}</strong><small>#{player.externalId}</small></span>
                <em>{t("playerSearch.recent")}</em>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="source-note">{t("playerSearch.coverage")}</p>
    </section>
  );
}
