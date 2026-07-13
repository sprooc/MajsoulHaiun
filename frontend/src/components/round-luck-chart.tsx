import { useTranslation } from "react-i18next";
import type { RoundLuckAnalysis } from "../api/client";
import { PLAYER_COLORS } from "./player-luck-comparison";


export function RoundLuckChart({ rounds }: { rounds: RoundLuckAnalysis[] }) {
  const { t, i18n } = useTranslation("analysis");
  const width = 720;
  const height = 250;
  const x = (round: number) => rounds.length <= 1 ? width / 2 : 48 + round * ((width - 96) / (rounds.length - 1));
  const y = (score: number) => 20 + (100 - score) * 2;
  const seats = rounds[0]?.players.map((player) => player.seat) ?? [];
  return (
    <section className="analysis-section">
      <div className="analysis-section__heading"><h2>{t("analysis.roundTrend")}</h2><span>0—100</span></div>
      <div className="chart-scroll">
        <svg className="round-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t("analysis.roundTrend")}>
          {[25, 50, 75].map((score) => <line key={score} x1="40" x2={width - 30} y1={y(score)} y2={y(score)} />)}
          {seats.map((seat, index) => {
            const points = rounds.map((round, roundIndex) => `${x(roundIndex)},${y(round.players.find((player) => player.seat === seat)?.score ?? 50)}`).join(" ");
            return <polyline key={seat} points={points} fill="none" stroke={PLAYER_COLORS[index % PLAYER_COLORS.length]} strokeWidth="4" strokeLinejoin="round" />;
          })}
          {rounds.flatMap((round, roundIndex) => round.players.map((player) => {
            const signedDelta = `${player.rawDelta >= 0 ? "+" : ""}${player.rawDelta.toFixed(3)}`;
            const signedPoints = `${player.actualPoints >= 0 ? "+" : ""}${player.actualPoints.toLocaleString(i18n.language)}`;
            const summary = t("analysis.roundPointSummary", {
              round: round.label,
              player: player.seat + 1,
              score: Math.round(player.score),
              zScore: player.zScore.toFixed(2),
              delta: signedDelta,
              confidence: t(`confidence.${player.confidence}`),
              actualPoints: signedPoints,
            });
            const colorIndex = seats.indexOf(player.seat);
            return (
              <circle
                key={`${round.roundIndex}-${player.seat}`}
                cx={x(roundIndex)}
                cy={y(player.score)}
                r="6"
                fill={PLAYER_COLORS[colorIndex % PLAYER_COLORS.length]}
                aria-label={summary}
                tabIndex={0}
              >
                <title>{summary}</title>
              </circle>
            );
          }))}
          {rounds.map((round, index) => <text key={round.roundIndex} x={x(index)} y="238" textAnchor="middle">{round.label}</text>)}
        </svg>
      </div>
    </section>
  );
}
