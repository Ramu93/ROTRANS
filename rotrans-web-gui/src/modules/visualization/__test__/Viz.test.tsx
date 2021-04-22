import React from "react";
import { render, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import { createMemoryHistory } from "history";
import { Router } from "react-router-dom";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import validators from "../../../fixtures/validators";
import Visualization from "../";
import graphdata from "../../../fixtures/graphdata";

const mockStore = configureStore([]);

const coreReducer = {
  validators: validators,
};

describe("Visualization Page", () => {
  let store;
  afterEach(cleanup);

  it("ToolBar title", () => {
    store = mockStore({
      coreReducer,
      vizReducer: {
        isLoading: false,
        dag: graphdata,
        selectedNodeId: "",
      },
    });

    const { getByTestId } = render(
      <Provider store={store}>
        <Visualization />
      </Provider>
    );
    expect(getByTestId("toolbarTitle")).toHaveTextContent("Visualization");
  });

  it("Selected node -> transaction", () => {
    store = mockStore({
      coreReducer,
      vizReducer: {
        isLoading: false,
        dag: graphdata,
        selectedNodeId: graphdata.nodes[4].id,
        isNodeDetailsFirstLoad: false,
      },
    });

    const { getAllByTestId } = render(
      <Provider store={store}>
        <Visualization />
      </Provider>
    );
    const content = getAllByTestId("nodeDetailsContent");
    expect(content[1]).toHaveTextContent("10");
    expect(content[2]).toHaveTextContent("9.8");
    expect(content[3]).toHaveTextContent("0.2");
  });

  it("Selected node -> acknowledgement", () => {
    store = mockStore({
      coreReducer,
      vizReducer: {
        isLoading: false,
        dag: graphdata,
        selectedNodeId: graphdata.nodes[0].id,
        isNodeDetailsFirstLoad: false,
      },
    });

    const { getAllByTestId } = render(
      <Provider store={store}>
        <Visualization />
      </Provider>
    );
    const content = getAllByTestId("nodeDetailsContent");
    expect(content[1]).toHaveTextContent("genesis1234");
    expect(content[2]).toHaveTextContent("txn1234");
    expect(content[3]).toHaveTextContent("validator1234");
  });
});
