import { useTranslation } from "react-i18next";
import type { AnalysisGameSummary } from "../api/client";
import type { ProvisionalGameSummary } from "../analysis/provisional-tasks";


export function GameSummary({ game }: { game: AnalysisGameSummary | ProvisionalGameSummary }) {
  const { t, i18n } = useTranslation("analysis");
  const players = [...(game.players ?? [])].sort((left, right) => left.seat - right.seat);

  return (
    <section className="game-summary" aria-labelledby="game-summary-title">
      <div className="analysis-section__heading">
        <h2 id="game-summary-title">{t("analysis.basicInfo")}</h2>
        <span>{game.mode ? t(`analysis.modes.${game.mode}`) : "—"}</span>
      </div>
      <div className="game-summary__meta">
        <span>{game.source ?? "—"}</span>
        <code>{game.externalId ?? "—"}</code>
        {"replayUrl" in game && game.replayUrl
          ? <a href={game.replayUrl} target="_blank" rel="noreferrer">{t("analysis.viewReplay")}</a>
          : "replayUrl" in game ? <small>{t("analysis.noReplayLink")}</small> : null}
      </div>
      {!players.length ? <p className="empty-state">{t("analysis.replayDetailsPending")}</p> : <ol className="game-summary__players">
        {players.map((player) => (
          <li key={player.seat}>
            <span className="game-summary__rank">{t("analysis.rankValue", { rank: game.finalRanks?.[player.seat] ?? "—" })}</span>
            <strong>{player.name}</strong>
            <span>{game.finalScores?.[player.seat]?.toLocaleString(i18n.language) ?? "—"}</span>
          </li>
        ))}
      </ol>}
    </section>
  );
}
