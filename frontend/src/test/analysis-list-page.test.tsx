import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AnalysisListPage } from "../pages/analysis-list-page";
import type { AnalysisGameSummary } from "../api/client";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  localStorage.clear();
});


afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});


const fourPlayerGame = {
  id: "game-1",
  mode: "4p" as const,
  source: "majsoul",
  externalId: "record-1",
  replayUrl: "https://game.maj-soul.com/1/?paipu=record-1",
  players: [{ seat: 0, name: "A" }, { seat: 1, name: "B" }, { seat: 2, name: "C" }, { seat: 3, name: "D" }],
  finalScores: [31000, 25000, 23000, 21000],
  finalRanks: [1, 2, 3, 4],
};


function analysis(id: string, status: string, game: AnalysisGameSummary = fourPlayerGame, createdAt = "2026-07-14T12:00:00Z") {
  return { id, gameId: game.id, status, createdAt, game };
}


it("includes a provisional task while its replay is still loading", async () => {
  localStorage.setItem("haiun.provisionalAnalyses", JSON.stringify([{
    id: "provisional-1",
    status: "loading_replay",
    createdAt: "2026-07-14T12:30:00Z",
    game: {},
  }]));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], nextOffset: null }), { status: 200 })));

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  expect(await screen.findByText("牌谱加载中")).toBeInTheDocument();
  expect(screen.getAllByText("分析中").length).toBeGreaterThan(0);
});


it("shows pending and completed analyses and only links completed results", async () => {
  const threePlayerGame = {
    ...fourPlayerGame,
    id: "game-2",
    mode: "3p" as const,
    externalId: "record-2",
    replayUrl: "https://game.maj-soul.com/1/?paipu=record-2",
    players: [{ seat: 0, name: "东" }, { seat: 1, name: "南" }, { seat: 2, name: "西" }],
    finalScores: [42000, 35000, 28000],
    finalRanks: [1, 2, 3],
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    items: [
      analysis("pending-1", "pending"),
      analysis("completed-1", "completed", threePlayerGame, "2026-07-14T11:00:00Z"),
    ],
    nextOffset: null,
  }), { status: 200 })));

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "分析列表" })).toBeInTheDocument();
  expect(screen.getAllByText("分析中").length).toBeGreaterThan(0);
  expect(screen.getAllByText("分析完成").length).toBeGreaterThan(0);
  expect(screen.getByText("A · B · C · D")).toBeInTheDocument();
  expect(screen.getByText("东 · 南 · 西")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /A · B · C · D/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /东 · 南 · 西/ })).toHaveAttribute("href", "/results/completed-1");
  expect(fetch).toHaveBeenCalledWith("/api/analyses?offset=0&limit=100", expect.anything());
});


it("loads another page by appending and deduplicating analyses", async () => {
  const updatedGame = {
    ...fourPlayerGame,
    players: fourPlayerGame.players.map((player) => player.seat === 0 ? { ...player, name: "Updated A" } : player),
  };
  const secondGame = {
    ...fourPlayerGame,
    id: "game-2",
    players: [{ seat: 0, name: "E" }, { seat: 1, name: "F" }, { seat: 2, name: "G" }, { seat: 3, name: "H" }],
  };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({
      items: [analysis("completed-1", "completed")],
      nextOffset: 100,
    }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      items: [analysis("completed-1", "completed", updatedGame), analysis("completed-2", "completed", secondGame, "2026-07-13T12:00:00Z")],
      nextOffset: null,
    }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  expect(await screen.findByRole("link", { name: /A · B · C · D/ })).toHaveAttribute("href", "/results/completed-1");
  await userEvent.click(screen.getByRole("button", { name: "加载更多" }));

  expect(await screen.findByText("Updated A · B · C · D")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /^Updated A · B · C · D/ })).toHaveAttribute("href", "/results/completed-1");
  expect(screen.getByRole("link", { name: /^E · F · G · H/ })).toHaveAttribute("href", "/results/completed-2");
  expect(screen.getAllByRole("link")).toHaveLength(2);
  expect(fetchMock).toHaveBeenLastCalledWith("/api/analyses?offset=100&limit=100", expect.anything());
  expect(screen.queryByRole("button", { name: "加载更多" })).not.toBeInTheDocument();
});


it("keeps loaded analyses visible when loading another page fails", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({
      items: [analysis("completed-1", "completed")],
      nextOffset: 100,
    }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ code: "REQUEST_FAILED", message: "failed" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })));

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  const loaded = await screen.findByRole("link", { name: /A · B · C · D/ });
  await userEvent.click(screen.getByRole("button", { name: "加载更多" }));

  expect(await screen.findByText("分析列表加载失败，请稍后重试。")).toBeInTheDocument();
  expect(loaded).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "加载更多" })).toBeEnabled();
});


it("polls pending result URLs and updates a row without discarding loaded analyses", async () => {
  vi.useFakeTimers();
  const olderGame = {
    ...fourPlayerGame,
    id: "game-older",
    players: [{ seat: 0, name: "Old A" }, { seat: 1, name: "Old B" }, { seat: 2, name: "Old C" }, { seat: 3, name: "Old D" }],
  };
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    if (String(input) === "/api/results/pending-1") {
      return Promise.resolve(new Response(JSON.stringify(analysis("pending-1", "completed")), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({
      items: [analysis("pending-1", "pending"), analysis("completed-older", "completed", olderGame, "2026-07-10T12:00:00Z")],
      nextOffset: null,
    }), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<MemoryRouter><AnalysisListPage /></MemoryRouter>);

  await act(async () => { await Promise.resolve(); });
  expect(screen.getByText("A · B · C · D")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });

  expect(screen.getByRole("link", { name: /^A · B · C · D/ })).toHaveAttribute("href", "/results/pending-1");
  expect(screen.getByRole("link", { name: /^Old A · Old B · Old C · Old D/ })).toHaveAttribute("href", "/results/completed-older");
  expect(screen.getAllByRole("link")).toHaveLength(2);
  expect(fetchMock).toHaveBeenCalledWith("/api/results/pending-1", expect.anything());
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
