import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zhCN from "../locales/zh-CN/common.json";
import en from "../locales/en/common.json";
import zhSearch from "../locales/zh-CN/search.json";
import enSearch from "../locales/en/search.json";
import zhAnalysis from "../locales/zh-CN/analysis.json";
import enAnalysis from "../locales/en/analysis.json";

export type AppLanguage = "zh-CN" | "en";

const storedLanguage = localStorage.getItem("language");

void i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { common: zhCN, search: zhSearch, analysis: zhAnalysis },
    en: { common: en, search: enSearch, analysis: enAnalysis },
  },
  lng: storedLanguage === "en" ? "en" : "zh-CN",
  fallbackLng: "en",
  defaultNS: "common",
  ns: ["common", "search", "analysis"],
  interpolation: { escapeValue: false },
});

export async function setLanguage(language: AppLanguage): Promise<void> {
  localStorage.setItem("language", language);
  document.documentElement.lang = language;
  await i18n.changeLanguage(language);
}

export default i18n;
