import React from "react";
import ReactDOM from "react-dom";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import BalanceIndicator from "..";

describe("BalanceIndicator component", () => {
  afterEach(cleanup);

  it("Rendered", () => {
    const div = document.createElement("div");
    ReactDOM.render(<BalanceIndicator balance="123" />, div);
  });

  it("Rendered with props", () => {
    const { getByTestId } = render(<BalanceIndicator balance="123" />);
    expect(getByTestId("balanceIndicatorValueText")).toHaveTextContent("123");
  });

  it("Matches snapshot", () => {
    const tree = renderer.create(<BalanceIndicator balance="123" />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
