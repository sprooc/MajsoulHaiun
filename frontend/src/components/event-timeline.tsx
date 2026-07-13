import { useTranslation } from "react-i18next";
import type { EventLuckDetail } from "../api/client";
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

export function EventTimeline({ events }: { events: EventLuckDetail[] }) {
  const { t } = useTranslation("analysis");
  return (
    <section className="analysis-section">
      <div className="analysis-section__heading"><h2>{t("analysis.timeline")}</h2><span>{events.length}</span></div>
      {!events.length ? <p>{t("analysis.noEvents")}</p> : (
        <ol className="event-timeline">
          {events.map((event, index) => (
            <li key={`${event.sequence}-${event.player}-${index}`} className={!event.includedInTotal ? "is-excluded" : ""}>
              <span className="event-sequence">{String(event.sequence).padStart(3, "0")}</span>
              <div className="event-main">
                <strong>{t(componentKeys[event.component] ?? event.component)}</strong>
                <small>P{event.player + 1}{!event.includedInTotal ? ` · ${t("analysis.excluded")}` : ""}</small>
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
