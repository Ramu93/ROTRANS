import { all, fork } from "redux-saga/effects";

import vizSaga from "../../modules/visualization/sagas";
import transactionsSaga from "../../modules/transactions/sagas";
import getValidatorsSaga from "./getValidarosSaga";
import stakeSaga from "../../modules/stake/sagas";

export default function* rootSaga() {
  yield all([
    fork(vizSaga),
    fork(transactionsSaga),
    fork(getValidatorsSaga),
    fork(stakeSaga),
  ]);
}
