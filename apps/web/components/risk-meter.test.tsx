import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RiskMeter } from "@/components/risk-meter";

describe("RiskMeter", () => {
  it("renders score and band", () => {
    render(<RiskMeter score={72} band="high" />);
    expect(screen.getByText("72/100")).toBeInTheDocument();
    expect(screen.getByText("Current band: high")).toBeInTheDocument();
  });
});
