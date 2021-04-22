import React from "react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import Loader from "..";

describe("Loader component", () => {
  it("Matches snapshot - visible", () => {
    const tree = renderer.create(<Loader visible />).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches snapshot - invisible", () => {
    const tree = renderer.create(<Loader visible={false} />).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
