import React from "react";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import Modal from "..";

describe("Modal component", () => {
  afterEach(cleanup);

  const something = <div data-testid="something"></div>;

  it("Rendered with only close button", () => {
    const { getByTestId } = render(
      <Modal show handleClose={() => {}}>
        {something}
      </Modal>
    );
    expect(getByTestId("something")).toBeVisible();
    expect(getByTestId("modalCloseBtn")).toBeVisible();
  });

  it("Rendered with action button", () => {
    const { getByTestId } = render(
      <Modal
        show
        handleClose={() => {}}
        confirmLabel="test confirm"
        handleConfirm={() => {}}
      >
        {something}
      </Modal>
    );
    expect(getByTestId("something")).toBeVisible();
    expect(getByTestId("modalCloseBtn")).toBeVisible();
    expect(getByTestId("modalActionBtn")).toBeVisible();
    expect(getByTestId("modalActionBtn")).toHaveTextContent("test confirm");
  });
});
