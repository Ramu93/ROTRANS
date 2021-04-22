import React from "react";
import { Switch, Route, Redirect } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";
import { ToastContainer } from "react-toastify";

import "./css/App.css";
import Visualization from "../visualization";
import Transactions from "../transactions";
import Stake from "../stake";

function App() {
  console.warn = console.error = () => {};

  return (
    <>
      <Switch>
        <Route exact path="/:port/visualization" component={Visualization} />
        <Route
          exact
          path="/:port/transactions/:value?/:recipient?"
          component={Transactions}
        />
        <Route exact path="/:port/stake" component={Stake} />
      </Switch>
      <ToastContainer />
    </>
  );
}

export default App;
