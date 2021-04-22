import { call, put, takeEvery } from "redux-saga/effects";
import { getTransactionInfo, getTransactionInfoSuccess } from "../actions";

import { BASE_URL } from "../../../utils";

async function fetchTransactionInfo(transactionId, port) {
  let data = null;
  try {
    const response = await fetch(
      BASE_URL + "transaction?txn_id=" + transactionId + "&port=" + port
    );
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const { transactionId, port } = payload;
    const transactionInfo = yield call(
      fetchTransactionInfo,
      transactionId,
      port
    );
    yield put(
      getTransactionInfoSuccess({
        transactionInfo,
      })
    );
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getTransactionInfo, handler);
}
