import { useTranslation } from "react-i18next";
import type { PlayerLuckAnalysis } from "../api/client";


const labels: Record<string, string> = {
  initial_hand: "analysis.initialHand",
  self_draw: "analysis.selfDraw",
  dora_reveal: "analysis.doraReveal",
  special_random: "analysis.specialRandom",
  opponent_gift: "analysis.opponentGift",
};

export function ComponentBreakdown({ players }: { players: PlayerLuckAnalysis[] }) {
  const { t } = useTranslation("analysis");
  const components = [...new Set(players.flatMap((player) => Object.keys(player.components)))];
  return (
    <section className="analysis-section">
      <div className="analysis-section__heading"><h2>{t("analysis.components")}</h2></div>
      <div className="component-list">
        {components.map((component) => (
          <div key={component} className="component-row">
            <strong>{t(labels[component] ?? component)}</strong>
            <div>{players.map((player) => <span key={player.seat} className={player.components[component] >= 0 ? "is-positive" : "is-negative"}>{player.name} {player.components[component]?.toFixed(3) ?? "—"}</span>)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
