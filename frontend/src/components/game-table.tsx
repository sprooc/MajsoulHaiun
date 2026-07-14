import { useTranslation } from "react-i18next";
import type { RemoteGame } from "../api/client";


function playerId(player: Record<string, unknown>): string | null {
  const value = player.accountId ?? player.account_id ?? player.id ?? player.externalId;
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function ResultValues({ game, values, highlightedPlayerId }: { game: RemoteGame; values: number[]; highlightedPlayerId?: string }) {
  return (
    <span className="game-table-values">
      {values.map((value, index) => {
        const highlighted = highlightedPlayerId !== undefined && playerId(game.players[index] ?? {}) === highlightedPlayerId;
        const content = value.toLocaleString();
        return <span key={index}>{index > 0 && <i> / </i>}{highlighted ? <strong>{content}</strong> : content}</span>;
      })}
    </span>
  );
}

export function GameTable({
  games,
  onImport,
  highlightedPlayerId,
}: {
  games: RemoteGame[];
  onImport?: (game: RemoteGame) => void;
  highlightedPlayerId?: string;
}) {
  const { t, i18n } = useTranslation("search");
  if (!games.length) return <p className="empty-state">{t("gameTable.empty")}</p>;
  return (
    <div className="game-table-wrap">
      <table className="game-table">
        <thead><tr><th>{t("gameTable.date")}</th><th>{t("gameTable.mode")}</th><th>{t("gameTable.players")}</th><th>{t("gameTable.scores")}</th><th>{t("gameTable.ranks")}</th><th /></tr></thead>
        <tbody>
          {games.map((game) => (
            <tr key={game.uuid}>
              <td>{game.startedAt ? new Intl.DateTimeFormat(i18n.language).format(new Date(game.startedAt * 1000)) : "—"}</td>
              <td>{game.mode === "4p" ? t("playerSearch.fourPlayer") : t("playerSearch.threePlayer")}</td>
              <td>{game.players.map((player) => String(player.nickname ?? "—")).join(" · ")}</td>
              <td>{game.scores.length ? <ResultValues game={game} values={game.scores} highlightedPlayerId={highlightedPlayerId} /> : "—"}</td>
              <td>{game.ranks?.length ? <ResultValues game={game} values={game.ranks} highlightedPlayerId={highlightedPlayerId} /> : "—"}</td>
              <td><button type="button" onClick={() => onImport?.(game)}>{t("gameTable.analyze")}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
