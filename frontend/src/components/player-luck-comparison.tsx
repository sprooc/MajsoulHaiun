import { useTranslation } from "react-i18next";
import type { PlayerLuckAnalysis } from "../api/client";


export const PLAYER_COLORS = ["#186b5b", "#d06343", "#526d87", "#9a7a35"];

export function PlayerLuckComparison({ players, finalScores }: { players: PlayerLuckAnalysis[]; finalScores?: number[] }) {
  const { t } = useTranslation("analysis");
  return (
    <div className="player-comparison">
      {players.map((player, index) => (
        <article key={player.seat} style={{ "--player-color": PLAYER_COLORS[index % PLAYER_COLORS.length] } as React.CSSProperties}>
          <div className="player-name"><span>{player.seat + 1}</span><strong>{player.name}</strong></div>
          <div className="luck-number" data-testid="player-luck-score">{Math.round(player.score)}</div>
          <dl>
            <div><dt>{t("analysis.luckScore")}</dt><dd>z {player.zScore.toFixed(2)}</dd></div>
            <div><dt>{t("analysis.finalScore")}</dt><dd>{(finalScores?.[player.seat] ?? player.actualPoints).toLocaleString()}</dd></div>
            <div><dt>{t("analysis.confidence")}</dt><dd>{t(`confidence.${player.confidence}`)}</dd></div>
          </dl>
        </article>
      ))}
    </div>
  );
}
