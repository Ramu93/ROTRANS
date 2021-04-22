import React from "react";
import ReactDOM from "react-dom";
import "./index.css";
import App from "./modules/app/App";
import * as serviceWorker from "./serviceWorker";
import { BrowserRouter } from "react-router-dom";
import { applyMiddleware, createStore, compose } from "redux";
import createSagaMiddleware from "redux-saga";
import { Provider } from "react-redux";
import rootSaga from './core/sagas';
import reducers from './core/reducers';
import 'font-awesome/css/font-awesome.min.css';

const composeEnhancers = window['__REDUX_DEVTOOLS_EXTENSION_COMPOSE__'] as typeof compose || compose;
const sagaMiddleware = createSagaMiddleware({});

const store = createStore(
  reducers,
  composeEnhancers(applyMiddleware(sagaMiddleware))
);

sagaMiddleware.run(rootSaga);
ReactDOM.render(
  <Provider store={store}>
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  </Provider>,
  document.getElementById("root")
);

// If you want your app to work offline and load faster, you can change
// unregister() to register() below. Note this comes with some pitfalls.
// Learn more about service workers: https://bit.ly/CRA-PWA
serviceWorker.unregister();
