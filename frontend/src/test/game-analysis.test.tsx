import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { GameAnalysisPage } from "../pages/game-analysis-page";
import type { GameLuckAnalysis } from "../api/client";
import { setLanguage } from "../i18n";


const fixtureAnalysis: GameLuckAnalysis = {
  analysisSchemaVersion: "1.0.0",
  gameHash: "fixture",
  algorithmId: "baseline-v1",
  algorithmVersion: "1.0.0",
  options: { eventDetails: true },
  players: [
    {
      seat: 0,
      name: "东家",
      rawDelta: 0.7,
      variance: 0.2,
      zScore: 1.47,
      score: 72,
      confidence: "medium",
      actualPoints: 31200,
      components: { initial_hand: 0.2, self_draw: 0.5 },
    },
    {
      seat: 1,
      name: "南家",
      rawDelta: -0.4,
      variance: 0.3,
      zScore: -0.73,
      score: 39,
      confidence: "medium",
      actualPoints: 18100,
      components: { initial_hand: -0.1, self_draw: -0.3 },
    },
  ],
  rounds: [
    {
      roundIndex: 0,
      label: "east-1",
      players: [
        { seat: 0, rawDelta: 0.7, variance: 0.2, zScore: 1.47, score: 72, confidence: "medium", actualPoints: 8000 },
        { seat: 1, rawDelta: -0.4, variance: 0.3, zScore: -0.73, score: 39, confidence: "medium", actualPoints: -8000 },
      ],
      events: [
        {
          sequence: 1,
          player: 0,
          component: "self_draw",
          actual: 0.8,
          expected: 0.5,
          delta: 0.3,
          variance: 0.04,
          zScore: 1.5,
          includedInTotal: true,
          tile: "0m",
          explanationKey: "analysis.selfDraw",
          features: { candidateCount: 63 },
        },
      ],
    },
  ],
};


beforeEach(async () => {
  await setLanguage("zh-CN");
});


it("shows luck score separately from the raw final score", () => {
  render(<GameAnalysisPage analysis={fixtureAnalysis} />);
  expect(screen.getByText("72")).toBeInTheDocument();
  expect(screen.getByText("31,200")).toBeInTheDocument();
  expect(screen.queryByText("+31,200")).not.toBeInTheDocument();
  expect(screen.getByText("实战点数不等于牌运")).toBeInTheDocument();
});


it("renders accessible red-five information in the event timeline", () => {
  render(<GameAnalysisPage analysis={fixtureAnalysis} />);
  expect(screen.getByLabelText("赤五万")).toBeInTheDocument();
  expect(screen.getByText("σ 0.200")).toBeInTheDocument();
  expect(screen.getByText("候选牌数：63")).toBeInTheDocument();
  expect(within(screen.getByRole("list")).queryByText("不计入主牌运", { exact: false })).not.toBeInTheDocument();
});


it("exposes complete round point details to chart users", () => {
  render(<GameAnalysisPage analysis={fixtureAnalysis} />);
  expect(screen.getByLabelText("east-1 P1：牌运 72，z 1.47，随机偏差 +0.700，置信度 中，实战点数 +8,000")).toBeInTheDocument();
});


it("filters event details and shows player names instead of seat placeholders", async () => {
  const filteredAnalysis: GameLuckAnalysis = {
    ...fixtureAnalysis,
    rounds: [{
      ...fixtureAnalysis.rounds[0],
      events: [
        ...fixtureAnalysis.rounds[0].events,
        {
          sequence: 2,
          player: 1,
          component: "opponent_gift",
          actual: 0.4,
          expected: 0.2,
          delta: 0.2,
          variance: 0.01,
          zScore: 2,
          includedInTotal: false,
          explanationKey: "analysis.opponentGift",
          features: {},
        },
      ],
    }],
  };

  render(<GameAnalysisPage analysis={filteredAnalysis} />);
  const timeline = screen.getByRole("list");
  expect(within(timeline).getByText("东家")).toBeInTheDocument();
  expect(within(timeline).getByText(/南家/)).toBeInTheDocument();
  expect(within(timeline).queryByText("P1")).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("玩家"), "1");
  expect(within(timeline).queryByText("东家")).not.toBeInTheDocument();
  expect(within(timeline).getByText(/南家/)).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("事件类型"), "self_draw");
  expect(screen.getByText("没有符合当前筛选条件的事件")).toBeInTheDocument();
});


it("loads registered algorithms and requests reanalysis", async () => {
  const updated = { ...fixtureAnalysis, algorithmId: "alternative-v1", algorithmVersion: "2.0.0" };
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { id: "baseline-v1", version: "1.0.0", nameKey: "algorithms.baselineV1.name", descriptionKey: "algorithms.baselineV1.description", supports: ["4p", "3p"] },
        { id: "alternative-v1", version: "2.0.0", nameKey: "alternative", descriptionKey: "alternative.desc", supports: ["4p"] },
      ]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "analysis-2", status: "completed", result: updated }), { status: 200 })),
  );
  const onAnalysis = vi.fn();
  render(<GameAnalysisPage analysis={fixtureAnalysis} gameId="game-1" onAnalysis={onAnalysis} />);
  expect(await screen.findByText("机会质量基线")).toBeInTheDocument();
  expect(screen.getByText("四人麻将 · 三人麻将", { exact: false })).toBeInTheDocument();
  await userEvent.selectOptions(await screen.findByLabelText("分析算法"), "alternative-v1");
  await userEvent.click(screen.getByRole("button", { name: "重新分析" }));
  expect(onAnalysis).toHaveBeenCalledWith(updated);
  expect(fetch).toHaveBeenLastCalledWith("/api/analyses", expect.objectContaining({ body: expect.stringContaining("alternative-v1") }));
});
