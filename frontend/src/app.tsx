import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import "./i18n";
import { setLanguage } from "./i18n";
import { HomePage } from "./pages/home-page";
import { SettingsPage } from "./pages/settings-page";
import { AnalysisDetailPage } from "./pages/analysis-detail-page";
import { AnalysisListPage } from "./pages/analysis-list-page";
import { AdminAccessPage } from "./pages/admin-access-page";
import { AccessProvider, RequireAdmin, useAccess } from "./access/access-context";


type HealthState = "checking" | "online" | "offline";

function HealthStatus() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<HealthState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/health", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("health check failed");
        setStatus("online");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setStatus("offline");
      });
    return () => controller.abort();
  }, []);

  return <div className={`health health--${status}`} aria-live="polite"><span className="health__dot" aria-hidden="true" />{t(`health.${status}`)}</div>;
}

function Shell() {
  const { t } = useTranslation();
  const { role, logout } = useAccess();
  const navigate = useNavigate();

  async function leaveAdmin() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/" aria-label={t("app.title")}>
          <span className="brand__mark" aria-hidden="true">牌</span>
          <span><strong>{t("app.romanized")}</strong><small>{t("app.title")}</small></span>
        </NavLink>
        <nav aria-label={t("app.navLabel")}>
          <NavLink to="/">{t("app.nav.search")}</NavLink>
          {role === "admin" && <NavLink to="/analyses">{t("app.nav.analysis")}</NavLink>}
          <NavLink to="/settings">{t("app.nav.settings")}</NavLink>
        </nav>
        <div className="topbar__tools">
          <HealthStatus />
          {role === "admin" && <button className="admin-logout" type="button" onClick={() => void leaveAdmin()}>{t("access.logout")}</button>}
          <div className="language-switcher">
            <button type="button" onClick={() => void setLanguage("zh-CN")}>{t("language.chinese")}</button>
            <button type="button" onClick={() => void setLanguage("en")}>{t("language.english")}</button>
          </div>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/analyses" element={<RequireAdmin><AnalysisListPage /></RequireAdmin>} />
        <Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} />
        <Route path="/admin" element={<AdminAccessPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<HomePage />} />
      </Routes>
    </div>
  );
}

export function App() {
  return <BrowserRouter><AccessProvider><Shell /></AccessProvider></BrowserRouter>;
}
