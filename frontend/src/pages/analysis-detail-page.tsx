import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getAnalysis, type AnalysisEnvelope, type GameLuckAnalysis } from "../api/client";
import { GameSummary } from "../components/game-summary";
import { GameAnalysisPage } from "./game-analysis-page";
import {
  getProvisionalAnalysis,
  PROVISIONAL_ANALYSES_EVENT,
  removeProvisionalAnalysis,
  type ProvisionalAnalysisTask,
} from "../analysis/provisional-tasks";


interface AnalysisLocationState {
  analysis?: AnalysisEnvelope;
  provisional?: ProvisionalAnalysisTask;
}

function withFinalScores(analysis: GameLuckAnalysis, finalScores: number[]): GameLuckAnalysis {
  return {
    ...analysis,
    players: analysis.players.map((player) => ({
      ...player,
      actualPoints: finalScores[player.seat] ?? player.actualPoints,
    })),
  };
}

export function AnalysisDetailPage() {
  const { t } = useTranslation("analysis");
  const { analysisId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const initial = (location.state as AnalysisLocationState | null)?.analysis ?? null;
  const provisionalInitial = (location.state as AnalysisLocationState | null)?.provisional
    ?? (analysisId ? getProvisionalAnalysis(analysisId) : null);
  const isProvisional = Boolean(analysisId?.startsWith("provisional-"));
  const [provisional, setProvisional] = useState<ProvisionalAnalysisTask | null>(provisionalInitial);
  const [envelope, setEnvelope] = useState<AnalysisEnvelope | null>(initial?.id === analysisId ? initial : null);
  const [state, setState] = useState<"loading" | "ready" | "error">(initial?.id === analysisId ? "ready" : "loading");
  const [completedNotice, setCompletedNotice] = useState(false);
  const previousStatus = useRef(initial?.status);

  useEffect(() => {
    if (!analysisId || isProvisional) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const next = await getAnalysis(analysisId, controller.signal);
        if ((previousStatus.current === "pending" || previousStatus.current === "analyzing") && next.status === "completed") {
          setCompletedNotice(true);
        }
        previousStatus.current = next.status;
        setEnvelope(next);
        setState("ready");
        if (next.status === "pending" || next.status === "analyzing") {
          timer = window.setTimeout(() => void refresh(), 1500);
        }
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setState("error");
      }
    };
    if (envelope?.status === "pending" || envelope?.status === "analyzing") {
      timer = window.setTimeout(() => void refresh(), 1500);
    } else {
      void refresh();
    }
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [analysisId, isProvisional, location.key]);

  useEffect(() => {
    if (!analysisId || !isProvisional) return;
    const refresh = () => {
      const next = getProvisionalAnalysis(analysisId);
      if (next?.status === "resolved" && next.analysisId) {
        removeProvisionalAnalysis(next.id);
        navigate(`/analyses/${next.analysisId}`, { replace: true });
        return;
      }
      setProvisional(next);
    };
    refresh();
    window.addEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
    return () => window.removeEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
  }, [analysisId, isProvisional, navigate]);

  useEffect(() => {
    if (!completedNotice) return;
    const timer = window.setTimeout(() => setCompletedNotice(false), 5000);
    return () => window.clearTimeout(timer);
  }, [completedNotice]);

  if (isProvisional && provisional && provisional.status !== "resolved") {
    return (
      <main className="analysis-page">
        <header className="analysis-task-header">
          <div><p>{provisional.id}</p><h1>{t("analysis.detailTitle")}</h1><span>{t(`analysis.status.${provisional.status}`)}</span></div>
          <strong className={`analysis-status analysis-status--${provisional.status}`}>{t(`analysis.status.${provisional.status}`)}</strong>
        </header>
        <GameSummary game={provisional.game} />
        {provisional.status === "loading_replay" ? (
          <section className="analysis-waiting" aria-live="polite">
            <span className="analysis-waiting__mark" aria-hidden="true">牌</span>
            <div><h2>{t("analysis.replayLoadingMessage")}</h2><p>{t("analysis.replayLoadingHint")}</p></div>
          </section>
        ) : <p className="inline-error">{t("analysis.replayLoadingFailed")}</p>}
      </main>
    );
  }
  if (state === "error" || (isProvisional && !provisional)) return <main className="analysis-page"><p className="inline-error">{t("analysis.detailError")}</p></main>;
  if (state === "loading" || !envelope) return <main className="analysis-page"><p className="empty-state">{t("analysis.detailLoading")}</p></main>;

  return (
    <main className="analysis-page">
      <header className="analysis-task-header">
        <div>
          <p>{envelope.id}</p>
          <h1>{t("analysis.detailTitle")}</h1>
          <span>{t(`analysis.status.${envelope.status}`)}</span>
        </div>
        <strong className={`analysis-status analysis-status--${envelope.status}`}>{t(`analysis.status.${envelope.status}`)}</strong>
      </header>
      <GameSummary game={envelope.game} />
      {completedNotice && <p className="analysis-progress analysis-progress--complete" role="status">{t("analysis.completedNotice")}</p>}
      {(envelope.status === "pending" || envelope.status === "analyzing") && (
        <section className="analysis-waiting" aria-live="polite">
          <span className="analysis-waiting__mark" aria-hidden="true">牌</span>
          <div><h2>{t("analysis.pendingMessage")}</h2><p>{t("analysis.pendingHint")}</p></div>
        </section>
      )}
      {envelope.status === "failed" && <p className="inline-error">{t("analysis.failedMessage")}</p>}
      {envelope.status === "completed" && envelope.result && (
        <GameAnalysisPage
          analysis={withFinalScores(envelope.result, envelope.game.finalScores)}
          finalScores={envelope.game.finalScores}
          gameId={envelope.gameId}
          embedded
          showHeader={false}
          onAnalysisCreated={(next) => {
            setEnvelope(next);
            previousStatus.current = next.status;
            navigate(`/analyses/${next.id}`, { replace: true, state: { analysis: next } });
          }}
        />
      )}
    </main>
  );
}
