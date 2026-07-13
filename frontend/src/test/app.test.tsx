import { fireEvent, render, screen } from "@testing-library/react";
import { App } from "../app";

it("switches the application shell from Chinese to English", async () => {
  localStorage.clear();
  render(<App />);
  expect(await screen.findByRole("heading", { name: "牌运", level: 1 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(await screen.findByRole("heading", { name: "Luck Analysis", level: 1 })).toBeInTheDocument();
});
