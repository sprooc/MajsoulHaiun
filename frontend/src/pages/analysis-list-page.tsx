import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { listAnalyses, type AnalysisEnvelope } from "../api/client";
import {
  listProvisionalAnalyses,
  PROVISIONAL_ANALYSES_EVENT,
  type ProvisionalAnalysisTask,
} from "../analysis/provisional-tasks";


function playerNames(analysis: AnalysisEnvelope): string {
  return [...analysis.game.players]
    .sort((left, right) => left.seat - right.seat)
    .map((player) => player.name)
    .join(" · ");
}

export function AnalysisListPage() {
  const { t, i18n } = useTranslation("analysis");
  const [analyses, setAnalyses] = useState<AnalysisEnvelope[]>([]);
  const [provisional, setProvisional] = useState<ProvisionalAnalysisTask[]>(listProvisionalAnalyses);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const next = await listAnalyses(controller.signal);
        setAnalyses(next);
        setState("ready");
        if (next.some((analysis) => analysis.status === "pending" || analysis.status === "analyzing")) {
          timer = window.setTimeout(() => void refresh(), 3000);
        }
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setState("error");
      }
    };
    void refresh();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const refresh = () => setProvisional(listProvisionalAnalyses());
    window.addEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
    return () => window.removeEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
  }, []);

  const pending = analyses.filter((analysis) => analysis.status !== "completed");
  const completed = analyses.filter((analysis) => analysis.status === "completed");

  const cardBody = (analysis: AnalysisEnvelope) => (
    <>
      <div>
        <span>{t(`analysis.modes.${analysis.game.mode}`)}</span>
        <time>{new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(analysis.createdAt))}</time>
      </div>
      <strong>{playerNames(analysis)}</strong>
      <small>{analysis.game.finalScores.map((score) => score.toLocaleString(i18n.language)).join(" / ")}</small>
    </>
  );

  return (
    <main className="workspace analysis-list-page">
      <header className="page-title">
        <p>{t("analysis.listKicker")}</p>
        <h1>{t("analysis.listTitle")}</h1>
        <span>{t("analysis.listDescription")}</span>
      </header>
      {state === "loading" && <p className="empty-state">{t("analysis.listLoading")}</p>}
      {state === "error" && <p className="inline-error">{t("analysis.listError")}</p>}
      {state === "ready" && !analyses.length && !provisional.length && <p className="empty-state">{t("analysis.listEmpty")}</p>}
      {!!(pending.length || provisional.length) && (
        <section className="analysis-list-section" aria-labelledby="pending-analyses-title">
          <div className="analysis-section__heading"><h2 id="pending-analyses-title">{t("analysis.pendingTitle")}</h2><span>{pending.length + provisional.length}</span></div>
          <div className="analysis-task-list">
            {provisional.map((analysis) => (
              <article className="analysis-task analysis-task--pending" key={analysis.id}>
                <div>
                  <span>{analysis.game.mode ? t(`analysis.modes.${analysis.game.mode}`) : "—"}</span>
                  <time>{new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(analysis.createdAt))}</time>
                </div>
                <strong>{analysis.game.players?.map((player) => player.name).join(" · ") || t("analysis.replayLoading")}</strong>
                <small>{analysis.game.finalScores?.map((score) => score.toLocaleString(i18n.language)).join(" / ") || "—"}</small>
                <em>{analysis.status === "failed" ? t("analysis.failed") : t("analysis.pending")}</em>
              </article>
            ))}
            {pending.map((analysis) => (
              <article className="analysis-task analysis-task--pending" key={analysis.id}>
                {cardBody(analysis)}
                <em>{analysis.status === "failed" ? t("analysis.failed") : t("analysis.pending")}</em>
              </article>
            ))}
          </div>
        </section>
      )}
      {!!completed.length && (
        <section className="analysis-list-section" aria-labelledby="completed-analyses-title">
          <div className="analysis-section__heading"><h2 id="completed-analyses-title">{t("analysis.completedTitle")}</h2><span>{completed.length}</span></div>
          <div className="analysis-task-list">
            {completed.map((analysis) => (
              <Link className="analysis-task analysis-task--completed" key={analysis.id} to={`/analyses/${analysis.id}`} aria-label={`${playerNames(analysis)} · ${t("analysis.viewResult")}`}>
                {cardBody(analysis)}
                <em>{t("analysis.viewResult")}</em>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
