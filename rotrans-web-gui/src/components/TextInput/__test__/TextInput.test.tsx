import React from "react";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import TextInput from "..";

describe("TextInput component", () => {
  afterEach(cleanup);

  it("Rendered without button and hidden prop", () => {
    const { getByTestId } = render(<TextInput label="ABC" value="123" />);
    expect(getByTestId("textInputLabel")).toHaveTextContent("ABC");
    expect(getByTestId("textInput")).toHaveValue("123");
    expect(getByTestId("textInputMainDiv")).not.toHaveClass("text-div");
    expect(getByTestId("textInput")).not.toHaveClass("text-hide");
  });

  it("Rendered with button", () => {
    const { getByTestId } = render(
      <TextInput
        label="ABC"
        value="123"
        button={<img src={require("../../../assets/svg/lock.svg")} />}
      />
    );
    expect(getByTestId("textInputButton")).toBeVisible();
    expect(getByTestId("textInputMainDiv")).toHaveClass("text-div");
  });

  it("Rendered with breakline", () => {
    const { getByTestId } = render(<TextInput label="ABC" value="123" br />);
    expect(getByTestId("textInputBr")).toBeVisible();
  });

  it("Rendered with hidden prop", () => {
    const { getByTestId } = render(<TextInput label="ABC" value="123" hide />);
    expect(getByTestId("textInput")).toHaveClass("text-hide");
  });

  it("Matches snapshot 1 - without button", () => {
    const tree = renderer
      .create(<TextInput label="ABC" value="123" />)
      .toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches snapshot 2 - with button", () => {
    const tree = renderer
      .create(
        <TextInput
          label="ABC"
          value="123"
          button={<img src={require("../../../assets/svg/lock.svg")} />}
        />
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches snapshot 3 - with button, hidden prop, br", () => {
    const tree = renderer
      .create(
        <TextInput
          label="ABC"
          value="123"
          button={<img src={require("../../../assets/svg/lock.svg")} />}
          hide
          br
        />
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });
});
