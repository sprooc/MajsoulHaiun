import { useTranslation } from "react-i18next";


export function Tile({ code, size = "compact" }: { code: string; size?: "compact" | "large" }) {
  const { t, i18n } = useTranslation("analysis");
  const red = code[0] === "0";
  const rank = red ? "5" : code[0];
  const suit = code[1] as "m" | "p" | "s" | "z";
  const accessible = i18n.language === "zh-CN"
    ? `${red ? t("tile.red") : ""}${t(`tile.ranks.${rank}`)}${t(`tile.suits.${suit}`)}`
    : `${red ? t("tile.red") : ""}${t(`tile.ranks.${rank}`)} ${t(`tile.suits.${suit}`)}`;
  return <span className={`tile tile--${size} ${red ? "tile--red" : ""}`} aria-label={accessible}><b>{rank}</b><small>{suit}</small>{red && <i aria-hidden="true">●</i>}</span>;
}
