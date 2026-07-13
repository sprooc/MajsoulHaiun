import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { createAnalysis, listAlgorithms, type AlgorithmDescription, type GameLuckAnalysis } from "../api/client";
import { ComponentBreakdown } from "../components/component-breakdown";
import { EventTimeline } from "../components/event-timeline";
import { PlayerLuckComparison } from "../components/player-luck-comparison";
import { RoundLuckChart } from "../components/round-luck-chart";


export function GameAnalysisPage({
  analysis,
  gameId,
  onAnalysis,
}: {
  analysis: GameLuckAnalysis;
  gameId?: string;
  onAnalysis?: (analysis: GameLuckAnalysis) => void;
}) {
  const { t } = useTranslation("analysis");
  const events = analysis.rounds.flatMap((round) => round.events);
  const [algorithms, setAlgorithms] = useState<AlgorithmDescription[]>([]);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState(analysis.algorithmId);
  const [reanalyzing, setReanalyzing] = useState(false);

  useEffect(() => {
    if (!gameId) return;
    void listAlgorithms().then(setAlgorithms);
  }, [gameId]);

  const registeredCurrent = algorithms.find((algorithm) => algorithm.id === analysis.algorithmId);
  const selectedDescription = algorithms.find((algorithm) => algorithm.id === selectedAlgorithm);
  const oldVersion = registeredCurrent && registeredCurrent.version !== analysis.algorithmVersion;

  async function reanalyze() {
    if (!gameId) return;
    setReanalyzing(true);
    try {
      const envelope = await createAnalysis(gameId, selectedAlgorithm);
      if (envelope.result) onAnalysis?.(envelope.result);
    } finally {
      setReanalyzing(false);
    }
  }

  return (
    <main className="analysis-page">
      <header className="analysis-header">
        <div><p>{analysis.algorithmId} · v{analysis.algorithmVersion}</p><h1>{t("analysis.title")}</h1><span>{t("analysis.subtitle")}</span></div>
        <div className="result-warning"><strong>{t("analysis.resultIsNotLuck")}</strong><p>{t("analysis.resultHint")}</p></div>
      </header>
      {gameId && (
        <div className="analysis-controls">
          <label>
            <span>{t("analysis.algorithmSelect")}</span>
            <select aria-label={t("analysis.algorithmSelect")} value={selectedAlgorithm} onChange={(event) => setSelectedAlgorithm(event.target.value)}>
              {algorithms.map((algorithm) => <option key={algorithm.id} value={algorithm.id}>{algorithm.id} · v{algorithm.version}</option>)}
            </select>
          </label>
          <button type="button" disabled={!algorithms.length || reanalyzing} onClick={() => void reanalyze()}>
            {reanalyzing ? t("analysis.reanalyzing") : t("analysis.reanalyze")}
          </button>
          {selectedDescription && (
            <div className="algorithm-summary">
              <strong>{t(selectedDescription.nameKey)}</strong>
              <span>{t(selectedDescription.descriptionKey)}</span>
              <small>
                v{selectedDescription.version} · {selectedDescription.supports.map((mode) => t(`analysis.modes.${mode}`)).join(" · ")}
              </small>
            </div>
          )}
          {oldVersion && <p className="analysis-version-warning">{t("analysis.olderVersion")}</p>}
        </div>
      )}
      <PlayerLuckComparison players={analysis.players} />
      <RoundLuckChart rounds={analysis.rounds} />
      <ComponentBreakdown players={analysis.players} />
      <EventTimeline events={events} />
    </main>
  );
}
