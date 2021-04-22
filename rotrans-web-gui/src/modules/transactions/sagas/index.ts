import { all, fork } from "redux-saga/effects";
import getKeysSaga from "./getKeysSaga";
import getBalanceSaga from "./getBalanceSaga";
import makeTransferSaga from "./makeTransferSaga";
import getAgentSaga from "./getAgentSaga";
import generateKeyPairSaga from "./generateKeyPairSaga";
import addKeySaga from "./addKeySaga";

export default function* transactionsSaga() {
  yield all([
    fork(getKeysSaga),
    fork(getBalanceSaga),
    fork(makeTransferSaga),
    fork(getAgentSaga),
    fork(generateKeyPairSaga),
    fork(addKeySaga),
  ]);
}
