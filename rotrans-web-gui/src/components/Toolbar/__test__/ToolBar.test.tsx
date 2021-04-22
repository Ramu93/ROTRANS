import React from "react";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import validators from "../../../fixtures/validators";
import ToolBar from "../";

const mockStore = configureStore([]);

describe("ToolBar component", () => {
  let store;

  afterEach(cleanup);

  it("Rendered with validators and without selected validator", () => {
    store = mockStore({
      coreReducer: {
        validators: validators,
      },
    });

    const { getByTestId } = render(
      <Provider store={store}>
        <ToolBar title="Transactions" showValidatorsList />
      </Provider>
    );
    expect(getByTestId("toolbarTitle")).toHaveTextContent("Transactions");
    expect(getByTestId("toolbarSelectedAgentName")).toHaveTextContent(
      validators[0].agentName
    );
    expect(getByTestId("toolbarSelectedAgentIp")).toHaveTextContent(
      validators[0].agentIp
    );
  });

  it("Rendered with selected validator", () => {
    store = mockStore({
      coreReducer: {
        validators: validators,
        rootValidator: validators[1],
      },
    });

    const { getByTestId } = render(
      <Provider store={store}>
        <ToolBar title="Transactions" showValidatorsList />
      </Provider>
    );
    expect(getByTestId("toolbarSelectedAgentName")).toHaveTextContent(
      validators[1].agentName
    );
    expect(getByTestId("toolbarSelectedAgentIp")).toHaveTextContent(
      validators[1].agentIp
    );
  });

  it("Matches with snapshot - without selected validator", () => {
    store = mockStore({
      coreReducer: {
        validators: validators,
      },
    });

    const tree = renderer
      .create(
        <Provider store={store}>
          <ToolBar title="Visualization" showValidatorsList />
        </Provider>
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });

  it("Matches with snapshot - without selected validator", () => {
    store = mockStore({
      coreReducer: {
        validators: validators,
        rootValidator: validators[1],
      },
    });

    const tree = renderer
      .create(
        <Provider store={store}>
          <ToolBar title="Transactions" showValidatorsList />
        </Provider>
      )
      .toJSON();
    expect(tree).toMatchSnapshot();
  });
});
