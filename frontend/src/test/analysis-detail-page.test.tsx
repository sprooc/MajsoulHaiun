import { render, screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AnalysisDetailPage } from "../pages/analysis-detail-page";
import { setLanguage } from "../i18n";


const game = {
  id: "game-1",
  mode: "4p" as const,
  source: "majsoul",
  externalId: "record-1",
  replayUrl: "https://game.maj-soul.com/1/?paipu=record-1",
  players: [
    { seat: 0, name: "A" },
    { seat: 1, name: "B" },
    { seat: 2, name: "C" },
    { seat: 3, name: "D" },
  ],
  finalScores: [31200, 27400, 23300, 18100],
  finalRanks: [1, 2, 3, 4],
};

const result = {
  analysisSchemaVersion: "1.0.0",
  gameHash: "fixture",
  algorithmId: "baseline-v1",
  algorithmVersion: "1.0.0",
  options: { eventDetails: true },
  players: [
    { seat: 0, name: "A", rawDelta: 0.7, variance: 0.2, zScore: 1.47, score: 72, confidence: "medium", actualPoints: 6200, components: {} },
    { seat: 1, name: "B", rawDelta: 0, variance: 0.2, zScore: 0, score: 50, confidence: "medium", actualPoints: 27400, components: {} },
    { seat: 2, name: "C", rawDelta: 0, variance: 0.2, zScore: 0, score: 50, confidence: "medium", actualPoints: 23300, components: {} },
    { seat: 3, name: "D", rawDelta: 0, variance: 0.2, zScore: 0, score: 50, confidence: "medium", actualPoints: 18100, components: {} },
  ],
  rounds: [],
};


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  localStorage.clear();
});


it("renders a provisional task without requesting a backend analysis id", async () => {
  localStorage.setItem("haiun.provisionalAnalyses", JSON.stringify([{
    id: "provisional-1",
    status: "loading_replay",
    createdAt: "2026-07-14T12:30:00Z",
    game: {},
  }]));
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter initialEntries={["/analyses/provisional-1"]}>
      <Routes><Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} /></Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("牌谱加载中，任务已加入分析列表。" )).toBeInTheDocument();
  expect(screen.getByText("牌谱加载后显示对局信息")).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});


it("shows basic game facts while pending, then adds the completed result and reminder", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "analysis-1", gameId: "game-1", status: "pending", createdAt: "2026-07-14T12:00:00Z", game,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "analysis-1", gameId: "game-1", status: "completed", createdAt: "2026-07-14T12:00:00Z", game, result,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { id: "baseline-v1", version: "1.0.0", nameKey: "algorithms.baselineV1.name", descriptionKey: "algorithms.baselineV1.description", supports: ["4p", "3p"] },
      ]), { status: 200 })),
  );

  render(
    <MemoryRouter initialEntries={["/analyses/analysis-1"]}>
      <Routes><Route path="/analyses/:analysisId" element={<AnalysisDetailPage />} /></Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("分析中，结果会自动补充到本页。" )).toBeInTheDocument();
  expect(screen.getByText("31,200")).toBeInTheDocument();
  expect(screen.getByText("第 1 名")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看原始牌谱" })).toHaveAttribute("href", game.replayUrl);
  expect(screen.queryByTestId("player-luck-score")).not.toBeInTheDocument();

  expect(await screen.findByText("分析完成，结果已更新。", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getAllByTestId("player-luck-score")).toHaveLength(4);
  expect(screen.getAllByText("终局点数").length).toBeGreaterThan(0);
  expect(screen.getAllByText("31,200")).toHaveLength(2);
  expect(screen.queryByText("+31,200")).not.toBeInTheDocument();
});
