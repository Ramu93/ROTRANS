import React from "react";
import { render, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import renderer from "react-test-renderer";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import validators from "../../../fixtures/validators";
import { key } from "../../../fixtures/constants";
import Transactions from "../";

const renderWithRouter = (ui, { route }) => {
  window.history.pushState({}, "Transactions", route);

  return render(ui, { wrapper: MemoryRouter });
};

const mockStore = configureStore([]);

const coreReducer = {
  validators: validators,
};

describe("Transactions Page", () => {
  let store;
  afterEach(cleanup);

  it("ToolBar title", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions" }
    );
    expect(getByTestId("toolbarTitle")).toHaveTextContent("Transactions");
  });

  xit("Public key field value", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getAllByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions" }
    );
    console.log(getAllByTestId("textInput")[0]);
    expect(getAllByTestId("textInput")[0]).toHaveValue(key);
  });

  it("Secret key field toggle hide/show", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getAllByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions" }
    );
    const input = getAllByTestId("textInput")[1];
    const button = getAllByTestId("textInputButton")[1];
    expect(input).toHaveClass("text-hide");
    fireEvent.click(button);
    expect(input).not.toHaveClass("text-hide");
    fireEvent.click(button);
    expect(input).toHaveClass("text-hide");
  });

  it("Balance Indicator value", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions" }
    );
    expect(getByTestId("balanceIndicatorValueText")).toHaveTextContent(
      "100000"
    );
  });

  it("Test open close add key modal", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions" }
    );

    expect(getByTestId("modalMain")).not.toHaveClass("display-block");
    const floatButton = getByTestId("floatingActionBtn");
    fireEvent.click(floatButton);
    expect(getByTestId("modalMain")).toHaveClass("display-block");
  });

  xit("Test URL params with input fields", () => {
    store = mockStore({
      coreReducer,
      transactionsReducer: {
        isLoading: false,
        keys: [{ publicKey: key, secretKey: key }],
        balance: "100000",
      },
    });
    const { getAllByTestId } = renderWithRouter(
      <Provider store={store}>
        <Transactions />
      </Provider>,
      { route: "/transactions/2/abc" }
    );
    expect(getAllByTestId("textInput")[3]).toHaveValue("2");
    expect(getAllByTestId("textInput")[4]).toHaveValue("abc");
  });
});
