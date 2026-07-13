import { useTranslation } from "react-i18next";
import type { RemoteGame } from "../api/client";


export function GameTable({ games, onImport }: { games: RemoteGame[]; onImport?: (game: RemoteGame) => void }) {
  const { t, i18n } = useTranslation("search");
  if (!games.length) return <p className="empty-state">{t("gameTable.empty")}</p>;
  return (
    <div className="game-table-wrap">
      <table className="game-table">
        <thead><tr><th>{t("gameTable.date")}</th><th>{t("gameTable.mode")}</th><th>{t("gameTable.players")}</th><th>{t("gameTable.scores")}</th><th /></tr></thead>
        <tbody>
          {games.map((game) => (
            <tr key={game.uuid}>
              <td>{game.startedAt ? new Intl.DateTimeFormat(i18n.language).format(new Date(game.startedAt * 1000)) : "—"}</td>
              <td>{game.mode === "4p" ? t("playerSearch.fourPlayer") : t("playerSearch.threePlayer")}</td>
              <td>{game.players.map((player) => String(player.nickname ?? "—")).join(" · ")}</td>
              <td>{game.scores.map((score) => score.toLocaleString()).join(" / ")}</td>
              <td><button type="button" onClick={() => onImport?.(game)}>{t("gameTable.analyze")}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
