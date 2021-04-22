import { all, fork } from "redux-saga/effects";
import getDagSaga from "./getDagSaga";
import getTransactionInfoSaga from "./getTransactionInfoSaga";
import getCkptRoundStatusSaga from "./getCkptRoundStatusSaga";

export default function* vizSaga() {
  yield all([
    fork(getDagSaga),
    fork(getTransactionInfoSaga),
    fork(getCkptRoundStatusSaga),
  ]);
}
