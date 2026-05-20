import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressTracker } from "@/components/progress-tracker";

describe("ProgressTracker", () => {
  it("marks the current case workflow step", () => {
    render(<ProgressTracker current="analysis" />);

    const tracker = screen.getByLabelText("Case progress");
    expect(within(tracker).getByText("Case")).toBeInTheDocument();
    expect(within(tracker).getByText("Documents")).toBeInTheDocument();
    expect(within(tracker).getByText("Extraction")).toBeInTheDocument();
    expect(within(tracker).getByText("Analysis").parentElement!).toHaveAttribute("aria-current", "step");
    expect(within(tracker).getByText("Report").parentElement!).not.toHaveAttribute("aria-current");
  });
});
