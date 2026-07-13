import { useTranslation } from "react-i18next";


export function SettingsPage() {
  const { t } = useTranslation();
  return <main className="workspace"><header className="page-title"><p>HAIUN</p><h1>{t("app.nav.settings")}</h1></header></main>;
}
