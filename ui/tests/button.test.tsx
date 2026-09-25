import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui";

describe("Button", () => {
  it("renders children and defaults to type=button", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("respects an explicit type=submit", () => {
    render(<Button type="submit">Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute(
      "type",
      "submit",
    );
  });

  it("applies the destructive intent classes", () => {
    render(<Button intent="destructive">Delete</Button>);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("bg-destructive");
  });

  it("applies the icon size classes", () => {
    render(<Button size="icon" aria-label="open" />);
    const btn = screen.getByRole("button", { name: "open" });
    expect(btn.className).toContain("h-9");
    expect(btn.className).toContain("w-9");
  });

  it("forwards click events", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    screen.getByRole("button", { name: "Click" }).click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders left and right icon slots", () => {
    render(
      <Button leftIcon={<span data-testid="left" />} rightIcon={<span data-testid="right" />}>
        Label
      </Button>,
    );
    expect(screen.getByTestId("left")).toBeInTheDocument();
    expect(screen.getByTestId("right")).toBeInTheDocument();
  });
});
