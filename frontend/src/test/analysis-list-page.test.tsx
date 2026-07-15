import { render, screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AnalysisListPage } from "../pages/analysis-list-page";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  localStorage.clear();
});


it("includes a provisional task while its replay is still loading", async () => {
  localStorage.setItem("haiun.provisionalAnalyses", JSON.stringify([{
    id: "provisional-1",
    status: "loading_replay",
    createdAt: "2026-07-14T12:30:00Z",
    game: {},
  }]));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  expect(await screen.findByText("牌谱加载中")).toBeInTheDocument();
  expect(screen.getAllByText("分析中").length).toBeGreaterThan(0);
});


it("shows pending and completed analyses and only links completed results", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([
    {
      id: "pending-1",
      gameId: "game-1",
      status: "pending",
      createdAt: "2026-07-14T12:00:00Z",
      game: {
        id: "game-1",
        mode: "4p",
        source: "majsoul",
        externalId: "record-1",
        replayUrl: "https://game.maj-soul.com/1/?paipu=record-1",
        players: [{ seat: 0, name: "A" }, { seat: 1, name: "B" }, { seat: 2, name: "C" }, { seat: 3, name: "D" }],
        finalScores: [31000, 25000, 23000, 21000],
        finalRanks: [1, 2, 3, 4],
      },
    },
    {
      id: "completed-1",
      gameId: "game-2",
      status: "completed",
      createdAt: "2026-07-14T11:00:00Z",
      game: {
        id: "game-2",
        mode: "3p",
        source: "majsoul",
        externalId: "record-2",
        replayUrl: "https://game.maj-soul.com/1/?paipu=record-2",
        players: [{ seat: 0, name: "东" }, { seat: 1, name: "南" }, { seat: 2, name: "西" }],
        finalScores: [42000, 35000, 28000],
        finalRanks: [1, 2, 3],
      },
      result: { players: [], rounds: [] },
    },
  ]), { status: 200 })));

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "分析列表" })).toBeInTheDocument();
  expect(screen.getAllByText("分析中").length).toBeGreaterThan(0);
  expect(screen.getAllByText("分析完成").length).toBeGreaterThan(0);
  expect(screen.getByText("A · B · C · D")).toBeInTheDocument();
  expect(screen.getByText("东 · 南 · 西")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /A · B · C · D/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /东 · 南 · 西/ })).toHaveAttribute("href", "/results/completed-1");
});
