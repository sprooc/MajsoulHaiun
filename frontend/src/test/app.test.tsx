import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { App } from "../app";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  sessionStorage.clear();
  localStorage.clear();
});


it("restores the searched and selected player after visiting the analysis list", async () => {
  window.history.pushState({}, "", "/");
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    if (url === "/api/access") return Promise.resolve(new Response(JSON.stringify({ role: "admin" }), { status: 200 }));
    if (url.includes("/api/players/search")) return Promise.resolve(new Response(JSON.stringify([
      { source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p" },
    ]), { status: 200 }));
    if (url.includes("/games?")) return Promise.resolve(new Response(JSON.stringify({ games: [], nextCursor: null }), { status: 200 }));
    if (url === "/api/analyses") return Promise.resolve(new Response("[]", { status: 200 }));
    return Promise.resolve(new Response("{}", { status: 404 }));
  }));

  render(<App />);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));
  expect(await screen.findByRole("heading", { name: "近期对局" })).toBeInTheDocument();

  await userEvent.click(screen.getByRole("link", { name: "分析" }));
  expect(await screen.findByRole("heading", { name: "分析列表" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "牌谱" }));

  expect(await screen.findByRole("textbox", { name: "玩家名称" })).toHaveValue("A");
  expect(screen.getByRole("button", { name: /A/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "近期对局" })).toBeInTheDocument();
});

it("switches the application shell from Chinese to English", async () => {
  localStorage.clear();
  render(<App />);
  expect(await screen.findByRole("heading", { name: "牌运", level: 1 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(await screen.findByRole("heading", { name: "Luck Analysis", level: 1 })).toBeInTheDocument();
});


it("hides the analysis list from guests and redirects direct list access", async () => {
  window.history.pushState({}, "", "/analyses");
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    if (url === "/api/access") return Promise.resolve(new Response(JSON.stringify({ role: "guest" }), { status: 200 }));
    return Promise.resolve(new Response("{}", { status: 404 }));
  }));
  render(<App />);
  expect(await screen.findByRole("heading", { name: "牌运", level: 1 })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "分析" })).not.toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});
