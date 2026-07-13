import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { type GamePage, type RemotePlayer, listPlayerGames } from "../api/client";
import { GameTable } from "../components/game-table";


export function PlayerPage({ player }: { player: RemotePlayer }) {
  const { t } = useTranslation("search");
  const [page, setPage] = useState<GamePage>({ games: [] });
  useEffect(() => {
    const controller = new AbortController();
    void listPlayerGames(player, undefined, controller.signal).then(setPage);
    return () => controller.abort();
  }, [player]);
  return <main className="workspace"><header className="page-title"><p>{player.mode}</p><h1>{player.nickname}</h1></header><section className="work-section"><h2>{t("gameTable.title")}</h2><GameTable games={page.games} /></section></main>;
}
