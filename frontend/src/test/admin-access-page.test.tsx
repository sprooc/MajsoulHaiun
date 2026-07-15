import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { App } from "../app";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  window.history.pushState({}, "", "/admin");
});


it("uses the unlinked admin page to reveal the analysis list and logout", async () => {
  let role: "guest" | "admin" = "guest";
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    if (url === "/api/access") return Promise.resolve(new Response(JSON.stringify({ role }), { status: 200 }));
    if (url === "/api/admin/session" && init?.method === "POST") {
      role = "admin";
      return Promise.resolve(new Response(JSON.stringify({ role }), { status: 200 }));
    }
    if (url === "/api/admin/session" && init?.method === "DELETE") {
      role = "guest";
      return Promise.resolve(new Response(JSON.stringify({ role }), { status: 200 }));
    }
    if (url === "/api/analyses") return Promise.resolve(new Response("[]", { status: 200 }));
    return Promise.resolve(new Response("{}", { status: 404 }));
  }));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "管理员访问" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "管理员访问" })).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("管理员密码"), "correct-admin-password");
  await userEvent.click(screen.getByRole("button", { name: "进入分析列表" }));

  expect(await screen.findByRole("heading", { name: "分析列表" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "分析" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/analyses");

  await userEvent.click(screen.getByRole("button", { name: "退出管理员" }));
  expect(await screen.findByRole("heading", { name: "牌运", level: 1 })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "分析" })).not.toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});


it("shows a generic error for an incorrect password", async () => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    if (url === "/api/access") return Promise.resolve(new Response(JSON.stringify({ role: "guest" }), { status: 200 }));
    if (url === "/api/admin/session") return Promise.resolve(new Response(JSON.stringify({
      code: "ADMIN_AUTH_FAILED",
      message: "failed",
      parameters: {},
    }), { status: 401, headers: { "Content-Type": "application/json" } }));
    return Promise.resolve(new Response("{}", { status: 404 }));
  }));

  render(<App />);
  await userEvent.type(await screen.findByLabelText("管理员密码"), "wrong-admin-password");
  await userEvent.click(screen.getByRole("button", { name: "进入分析列表" }));

  expect(await screen.findByText("密码不正确或管理员访问尚未配置。")).toBeInTheDocument();
  expect(screen.getByLabelText("管理员密码")).toHaveValue("");
});
