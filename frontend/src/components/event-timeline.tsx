import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { EventLuckDetail, PlayerLuckAnalysis } from "../api/client";
import { Tile } from "./tile";


const componentKeys: Record<string, string> = {
  initial_hand: "analysis.initialHand",
  self_draw: "analysis.selfDraw",
  dora_reveal: "analysis.doraReveal",
  special_random: "analysis.specialRandom",
  opponent_gift: "analysis.opponentGift",
};

const featureKeys: Record<string, string> = {
  candidateCount: "analysis.featureCandidateCount",
  handSize: "analysis.featureHandSize",
  shanten: "analysis.featureShanten",
  dealer: "analysis.featureDealer",
  reason: "analysis.featureReason",
};

export function EventTimeline({ events, players }: { events: EventLuckDetail[]; players: PlayerLuckAnalysis[] }) {
  const { t } = useTranslation("analysis");
  const [component, setComponent] = useState("all");
  const [player, setPlayer] = useState("all");
  const [scope, setScope] = useState("all");
  const components = [...new Set(events.map((event) => event.component))];
  const playerNames = new Map(players.map((item) => [item.seat, item.name]));
  const filtered = events.filter((event) => (
    (component === "all" || event.component === component)
    && (player === "all" || event.player === Number(player))
    && (scope === "all" || (scope === "included" ? event.includedInTotal : !event.includedInTotal))
  ));
  return (
    <section className="analysis-section">
      <div className="analysis-section__heading"><h2>{t("analysis.timeline")}</h2><span>{filtered.length} / {events.length}</span></div>
      {!!events.length && <div className="event-filters">
        <label><span>{t("analysis.eventTypeFilter")}</span><select aria-label={t("analysis.eventTypeFilter")} value={component} onChange={(event) => setComponent(event.target.value)}>
          <option value="all">{t("analysis.filterAll")}</option>
          {components.map((value) => <option key={value} value={value}>{t(componentKeys[value] ?? value)}</option>)}
        </select></label>
        <label><span>{t("analysis.playerFilter")}</span><select aria-label={t("analysis.playerFilter")} value={player} onChange={(event) => setPlayer(event.target.value)}>
          <option value="all">{t("analysis.filterAll")}</option>
          {players.map((item) => <option key={item.seat} value={String(item.seat)}>{item.name}</option>)}
        </select></label>
        <label><span>{t("analysis.scopeFilter")}</span><select aria-label={t("analysis.scopeFilter")} value={scope} onChange={(event) => setScope(event.target.value)}>
          <option value="all">{t("analysis.filterAll")}</option>
          <option value="included">{t("analysis.filterIncluded")}</option>
          <option value="excluded">{t("analysis.filterExcluded")}</option>
        </select></label>
      </div>}
      {!events.length ? <p>{t("analysis.noEvents")}</p> : !filtered.length ? <p>{t("analysis.noFilteredEvents")}</p> : (
        <ol className="event-timeline">
          {filtered.map((event, index) => (
            <li key={`${event.sequence}-${event.player}-${index}`} className={!event.includedInTotal ? "is-excluded" : ""}>
              <span className="event-sequence">{String(event.sequence).padStart(3, "0")}</span>
              <div className="event-main">
                <strong>{t(componentKeys[event.component] ?? event.component)}</strong>
                <small>{playerNames.get(event.player) ?? `P${event.player + 1}`}{!event.includedInTotal ? ` · ${t("analysis.excluded")}` : ""}</small>
                {!!Object.keys(event.features).length && (
                  <span className="event-features">
                    {Object.entries(event.features).map(([key, value]) => (
                      <em key={key}>{t(featureKeys[key] ?? "analysis.feature", { name: key, value: String(value) })}</em>
                    ))}
                  </span>
                )}
              </div>
              {event.tile ? <Tile code={event.tile} /> : <span />}
              <dl>
                <div><dt>{t("analysis.actual")}</dt><dd>{event.actual.toFixed(3)}</dd></div>
                <div><dt>{t("analysis.expected")}</dt><dd>{event.expected.toFixed(3)}</dd></div>
                <div><dt>{t("analysis.delta")}</dt><dd className={event.delta >= 0 ? "is-positive" : "is-negative"}>{event.delta >= 0 ? "+" : ""}{event.delta.toFixed(3)}</dd></div>
                <div><dt>{t("analysis.zScore")}</dt><dd>z {event.zScore.toFixed(2)}</dd></div>
                <div><dt>{t("analysis.localStdDev")}</dt><dd>σ {Math.sqrt(event.variance).toFixed(3)}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
