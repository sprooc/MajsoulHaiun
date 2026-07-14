import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  createAnalysis,
  importReplayLocator,
  listPlayerGames,
  type RemoteGame,
  type RemotePlayer,
  type ReplayImportResult,
} from "../api/client";
import { GameTable } from "../components/game-table";
import { PlayerSearch } from "../components/player-search";
import { ReplayImport } from "../components/replay-import";
import {
  createProvisionalAnalysis,
  failProvisionalAnalysis,
  provisionalGameFromRemote,
  removeProvisionalAnalysis,
  type ProvisionalGameSummary,
} from "../analysis/provisional-tasks";


export function HomePage() {
  const { t } = useTranslation("search");
  const navigate = useNavigate();
  const [selected, setSelected] = useState<RemotePlayer | null>(null);
  const [games, setGames] = useState<RemoteGame[]>([]);
  const [gamesState, setGamesState] = useState<"idle" | "loading" | "error">("idle");
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [recentImportMessage, setRecentImportMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setGamesState("loading");
    setGames([]);
    setNextCursor(null);
    void listPlayerGames(selected, undefined, controller.signal)
      .then((page) => {
        setGames(page.games);
        setNextCursor(page.nextCursor ?? null);
        setGamesState("idle");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setGamesState("error");
      });
    return () => controller.abort();
  }, [selected]);

  async function loadMoreGames() {
    if (!selected || nextCursor === null) return;
    setLoadingMore(true);
    try {
      const page = await listPlayerGames(selected, nextCursor, new AbortController().signal);
      setGames((current) => [...current, ...page.games]);
      setNextCursor(page.nextCursor ?? null);
    } finally {
      setLoadingMore(false);
    }
  }

  function startProvisional(game: ProvisionalGameSummary = {}): string {
    const task = createProvisionalAnalysis(game);
    navigate(`/analyses/${task.id}`, { state: { provisional: task } });
    return task.id;
  }

  async function handleImported(result: ReplayImportResult, provisionalId?: string) {
    if (!result.gameId) {
      failProvisionalAnalysis(provisionalId);
      return;
    }
    try {
      const envelope = await createAnalysis(result.gameId);
      removeProvisionalAnalysis(provisionalId);
      navigate(`/analyses/${envelope.id}`, { replace: true, state: { analysis: envelope } });
    } catch {
      failProvisionalAnalysis(provisionalId);
    }
  }

  async function importRecentGame(game: RemoteGame) {
    setRecentImportMessage(null);
    const provisionalId = startProvisional(provisionalGameFromRemote(game));
    try {
      const result = await importReplayLocator(game.uuid);
      await handleImported(result, provisionalId);
    } catch (error) {
      failProvisionalAnalysis(provisionalId);
      setRecentImportMessage(
        error instanceof ApiError && error.code === "REPLAY_FETCH_UNAVAILABLE"
          ? t("replayImport.fetchUnavailable")
          : t("replayImport.error"),
      );
    }
  }

  return (
    <main className="workspace">
      <header className="workspace-intro">
        <p>{t("workspace.kicker")}</p>
        <h1>{t("workspace.title")}</h1>
        <span>{t("workspace.description")}</span>
        <div className="workspace-glyph" aria-hidden="true"><i>牌</i><i>運</i></div>
      </header>
      <PlayerSearch onSelect={setSelected} />
      {selected && <p className="selection-strip"><strong>{selected.nickname}</strong><span>{selected.mode}</span><small>#{selected.externalId}</small></p>}
      {selected && (
        <section className="work-section" aria-labelledby="recent-games-title">
          <div className="section-heading">
            <div><p className="section-index">02</p><h2 id="recent-games-title">{t("gameTable.title")}</h2></div>
            <p>{selected.nickname} · {selected.mode}</p>
          </div>
          {gamesState === "loading" ? <p className="empty-state">{t("playerSearch.loading")}</p> : <GameTable games={games} highlightedPlayerId={selected.externalId} onImport={(game) => void importRecentGame(game)} />}
          {gamesState === "error" && <p className="inline-error">{t("replayImport.error")}</p>}
          {recentImportMessage && <p className="inline-error" role="status">{recentImportMessage}</p>}
          {nextCursor !== null && <button className="load-more" type="button" disabled={loadingMore} onClick={() => void loadMoreGames()}>{t("gameTable.loadMore")}</button>}
        </section>
      )}
      <ReplayImport
        onImportStarted={(source) => startProvisional({ source })}
        onImported={(result, provisionalId) => void handleImported(result, provisionalId)}
        onImportFailed={failProvisionalAnalysis}
      />
    </main>
  );
}
