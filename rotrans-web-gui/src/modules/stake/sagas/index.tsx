import { all, fork } from "redux-saga/effects";
import getStakeDistSaga from "./getStakeDistSaga";

export default function* stakeSaga() {
  yield all([
    fork(getStakeDistSaga),
  ]);
}
