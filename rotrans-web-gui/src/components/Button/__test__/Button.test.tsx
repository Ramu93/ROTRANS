import React from "react";
import ReactDOM from "react-dom";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import Button from "..";

describe("Button component", () => {
  afterEach(cleanup);

  it("Rendered", () => {
    const div = document.createElement("div");
    ReactDOM.render(<Button label="Transfer" />, div);
  });

  it("Rendered with props", () => {
    const { getByTestId } = render(<Button label="Transfer" />);
    expect(getByTestId("label")).toHaveTextContent("Transfer");
  });

  it("Matches snapshot 1 - without icon", () => {
    const tree = renderer.create(<Button label="Transer" />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches snapshot 2 - with icon", () => {
    const tree = renderer
      .create(
        <Button
          label="Transfer"
          icon={<img src={require("../../../assets/svg/go.svg")} />}
        />
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });
});
