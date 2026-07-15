import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { createAnalysis, listAlgorithms, type AlgorithmDescription, type AnalysisEnvelope, type GameLuckAnalysis } from "../api/client";
import { ComponentBreakdown } from "../components/component-breakdown";
import { EventTimeline } from "../components/event-timeline";
import { PlayerLuckComparison } from "../components/player-luck-comparison";
import { RoundLuckChart } from "../components/round-luck-chart";
import { SelectMenu } from "../components/select-menu";


export function GameAnalysisPage({
  analysis,
  gameId,
  onAnalysis,
  onAnalysisCreated,
  embedded = false,
  showHeader = true,
  finalScores,
}: {
  analysis: GameLuckAnalysis;
  gameId?: string;
  onAnalysis?: (analysis: GameLuckAnalysis) => void;
  onAnalysisCreated?: (analysis: AnalysisEnvelope) => void;
  embedded?: boolean;
  showHeader?: boolean;
  finalScores?: number[];
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
      onAnalysisCreated?.(envelope);
    } finally {
      setReanalyzing(false);
    }
  }

  const content = (
    <>
      {showHeader && <header className="analysis-header">
        <div><p>{analysis.algorithmId} · v{analysis.algorithmVersion}</p><h1>{t("analysis.title")}</h1><span>{t("analysis.subtitle")}</span></div>
        <div className="result-warning"><strong>{t("analysis.resultIsNotLuck")}</strong><p>{t("analysis.resultHint")}</p></div>
      </header>}
      {!showHeader && <div className="result-warning result-warning--inline"><strong>{t("analysis.resultIsNotLuck")}</strong><p>{t("analysis.resultHint")}</p></div>}
      {gameId && (
        <div className="analysis-controls">
          <SelectMenu
            label={t("analysis.algorithmSelect")}
            value={selectedAlgorithm}
            options={algorithms.map((algorithm) => ({ value: algorithm.id, label: `${algorithm.id} · v${algorithm.version}` }))}
            onChange={setSelectedAlgorithm}
            disabled={!algorithms.length}
          />
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
      <PlayerLuckComparison players={analysis.players} finalScores={finalScores} />
      <RoundLuckChart rounds={analysis.rounds} />
      <ComponentBreakdown players={analysis.players} />
      <EventTimeline events={events} players={analysis.players} />
    </>
  );
  return embedded ? content : <main className="analysis-page">{content}</main>;
}
