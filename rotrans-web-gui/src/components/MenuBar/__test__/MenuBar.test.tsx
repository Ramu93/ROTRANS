import React from "react";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import { createMemoryHistory } from "history";
import { Router } from "react-router-dom";
import MenuBar from "..";

describe("MenuBar component", () => {
  afterEach(cleanup);

  it("Rendered visualization menu item", () => {
    const history = createMemoryHistory();
    const route = "/visualization";
    history.push(route);

    const { getByTestId } = render(
      <Router history={history}>
        <MenuBar />
      </Router>
    );
    expect(getByTestId("vizMenuItem")).toHaveClass("menu", "menu-active");
    expect(getByTestId("transactionsMenuItem")).toHaveClass("menu");
  });

  it("Rendered transactions menu item", () => {
    const history = createMemoryHistory();
    const route = "/transactions";
    history.push(route);

    const { getByTestId } = render(
      <Router history={history}>
        <MenuBar />
      </Router>
    );
    expect(getByTestId("vizMenuItem")).toHaveClass("menu");
    expect(getByTestId("transactionsMenuItem")).toHaveClass(
      "menu",
      "menu-active"
    );
  });

  it("Matches transactions snapshot ", () => {
    const history = createMemoryHistory();
    const route = "/transactions";
    history.push(route);

    const tree = renderer
      .create(
        <Router history={history}>
          <MenuBar />
        </Router>
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches visualization snapshot ", () => {
    const history = createMemoryHistory();
    const route = "/visualization";
    history.push(route);

    const tree = renderer
      .create(
        <Router history={history}>
          <MenuBar />
        </Router>
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });
});
