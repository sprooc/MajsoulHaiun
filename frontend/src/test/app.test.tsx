import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { App } from "../app";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
});

it("switches the application shell from Chinese to English", async () => {
  localStorage.clear();
  render(<App />);
  expect(await screen.findByRole("heading", { name: "牌运", level: 1 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(await screen.findByRole("heading", { name: "Luck Analysis", level: 1 })).toBeInTheDocument();
});


it("opens the analysis list from the main navigation", async () => {
  window.history.pushState({}, "", "/");
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    if (url === "/api/analyses") return Promise.resolve(new Response("[]", { status: 200 }));
    return Promise.resolve(new Response("{}", { status: 404 }));
  }));
  render(<App />);
  await userEvent.click(screen.getByRole("link", { name: "分析" }));
  expect(await screen.findByRole("heading", { name: "分析列表" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/analyses");
});
