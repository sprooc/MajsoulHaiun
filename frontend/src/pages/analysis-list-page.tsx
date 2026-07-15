import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { getAnalysis, listAnalyses, type AnalysisEnvelope, type AnalysisSummary } from "../api/client";
import {
  listProvisionalAnalyses,
  PROVISIONAL_ANALYSES_EVENT,
  type ProvisionalAnalysisTask,
} from "../analysis/provisional-tasks";


function playerNames(analysis: AnalysisSummary): string {
  return [...analysis.game.players]
    .sort((left, right) => left.seat - right.seat)
    .map((player) => player.name)
    .join(" · ");
}

function mergeAnalysisSummaries(current: AnalysisSummary[], incoming: AnalysisSummary[]): AnalysisSummary[] {
  const merged = [...current];
  const positions = new Map(merged.map((analysis, index) => [analysis.id, index]));
  for (const analysis of incoming) {
    const position = positions.get(analysis.id);
    if (position === undefined) {
      positions.set(analysis.id, merged.length);
      merged.push(analysis);
    } else {
      merged[position] = { ...merged[position], ...analysis };
    }
  }
  return merged;
}

function summarizeAnalysis(analysis: AnalysisEnvelope): AnalysisSummary {
  return {
    id: analysis.id,
    gameId: analysis.gameId,
    status: analysis.status,
    createdAt: analysis.createdAt,
    game: analysis.game,
    errorCode: analysis.errorCode,
  };
}

export function AnalysisListPage() {
  const { t, i18n } = useTranslation("analysis");
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [provisional, setProvisional] = useState<ProvisionalAnalysisTask[]>(listProvisionalAnalyses);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const page = await listAnalyses({ signal: controller.signal });
        setAnalyses(page.items);
        setNextOffset(page.nextOffset);
        setState("ready");
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setState("error");
      }
    };
    void refresh();
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      setProvisional(listProvisionalAnalyses());
      void listAnalyses({ signal: controller.signal }).then((page) => {
        setAnalyses(page.items);
        setNextOffset(page.nextOffset);
        setLoadMoreError(false);
        setState("ready");
      }).catch((error) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setState("error");
      });
    };
    window.addEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
    return () => {
      controller.abort();
      window.removeEventListener(PROVISIONAL_ANALYSES_EVENT, refresh);
    };
  }, []);

  const pollingKey = analyses
    .filter((analysis) => analysis.status === "pending" || analysis.status === "analyzing")
    .map((analysis) => analysis.id)
    .join("|");

  useEffect(() => {
    if (!pollingKey) return;
    const controller = new AbortController();
    const analysisIds = pollingKey.split("|");
    let stopped = false;
    let timer: number | undefined;

    const poll = async () => {
      const results = await Promise.allSettled(
        analysisIds.map((id) => getAnalysis(id, controller.signal)),
      );
      if (stopped) return;
      const updates = results
        .filter((result): result is PromiseFulfilledResult<AnalysisEnvelope> => result.status === "fulfilled")
        .map((result) => summarizeAnalysis(result.value));
      if (updates.length) setAnalyses((current) => mergeAnalysisSummaries(current, updates));
      if (!stopped) timer = window.setTimeout(() => void poll(), 3000);
    };

    timer = window.setTimeout(() => void poll(), 3000);
    return () => {
      stopped = true;
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [pollingKey]);

  const loadMore = async () => {
    if (nextOffset === null || loadingMore) return;
    setLoadingMore(true);
    setLoadMoreError(false);
    try {
      const page = await listAnalyses({ offset: nextOffset });
      setAnalyses((current) => mergeAnalysisSummaries(current, page.items));
      setNextOffset(page.nextOffset);
    } catch {
      setLoadMoreError(true);
    } finally {
      setLoadingMore(false);
    }
  };

  const pending = analyses.filter((analysis) => analysis.status !== "completed");
  const completed = analyses.filter((analysis) => analysis.status === "completed");

  const cardBody = (analysis: AnalysisSummary) => (
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
              <Link className="analysis-task analysis-task--completed" key={analysis.id} to={`/results/${analysis.id}`} aria-label={`${playerNames(analysis)} · ${t("analysis.viewResult")}`}>
                {cardBody(analysis)}
                <em>{t("analysis.viewResult")}</em>
              </Link>
            ))}
          </div>
        </section>
      )}
      {loadMoreError && <p className="inline-error" role="status">{t("analysis.listError")}</p>}
      {nextOffset !== null && (
        <button className="load-more" type="button" disabled={loadingMore} onClick={() => void loadMore()}>
          {t("analysis.listLoadMore")}
        </button>
      )}
    </main>
  );
}
