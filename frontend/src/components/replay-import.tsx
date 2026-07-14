import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, importReplayFile, importReplayLocator, type ReplayImportResult } from "../api/client";


interface ReplayImportProps {
  onImportStarted?: (source: "majsoul" | "local-file") => string | undefined;
  onImported?: (result: ReplayImportResult, provisionalId?: string) => void;
  onImportFailed?: (provisionalId?: string) => void;
}

export function ReplayImport({ onImportStarted, onImported, onImportFailed }: ReplayImportProps) {
  const { t } = useTranslation("search");
  const [locator, setLocator] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function importLocator(event: FormEvent) {
    event.preventDefault();
    const provisionalId = onImportStarted?.("majsoul");
    try {
      const result = await importReplayLocator(locator);
      if (result.parseErrorCode || !result.gameId) {
        setMessage(t("replayImport.parseFailed"));
        onImportFailed?.(provisionalId);
        return;
      }
      setMessage(t("replayImport.success"));
      onImported?.(result, provisionalId);
    } catch (error) {
      onImportFailed?.(provisionalId);
      setMessage(error instanceof ApiError && error.code === "REPLAY_FETCH_UNAVAILABLE"
        ? t("replayImport.fetchUnavailable")
        : t("replayImport.error"));
    }
  }

  async function importFile(event: FormEvent) {
    event.preventDefault();
    if (!file || file.size > 32 * 1024 * 1024) {
      setMessage(t("replayImport.error"));
      return;
    }
    const provisionalId = onImportStarted?.("local-file");
    try {
      const result = await importReplayFile(file);
      if (result.parseErrorCode || !result.gameId) {
        setMessage(t("replayImport.parseFailed"));
        onImportFailed?.(provisionalId);
        return;
      }
      setMessage(t("replayImport.success"));
      onImported?.(result, provisionalId);
    } catch {
      onImportFailed?.(provisionalId);
      setMessage(t("replayImport.error"));
    }
  }

  return (
    <section className="work-section import-section" aria-labelledby="replay-import-title">
      <div className="section-heading">
        <div><p className="section-index">03</p><h2 id="replay-import-title">{t("replayImport.title")}</h2></div>
        <p>{t("replayImport.description")}</p>
      </div>
      <div className="import-grid">
        <form onSubmit={(event) => void importLocator(event)}>
          <label><span>{t("replayImport.locator")}</span><input value={locator} onChange={(event) => setLocator(event.target.value)} placeholder={t("replayImport.locatorPlaceholder")} /></label>
          <button type="submit" disabled={!locator.trim()}>{t("replayImport.submitLocator")}</button>
        </form>
        <form onSubmit={(event) => void importFile(event)}>
          <label className="file-drop"><span>{file?.name ?? t("replayImport.chooseFile")}</span><input aria-label={t("replayImport.file")} type="file" accept=".json,.bin,.pb,application/json,application/octet-stream" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          <small>{t("replayImport.fileLimit")}</small>
          <button type="submit" disabled={!file}>{t("replayImport.submitFile")}</button>
        </form>
      </div>
      {message && <p className="import-message" role="status">{message}</p>}
    </section>
  );
}
