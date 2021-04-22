import { call, put, takeEvery } from "redux-saga/effects";
import { BASE_URL, formatNumber } from "../../../utils";
import { getAgent, getAgentSuccess } from "../actions";

async function fetchAgent({ port }) {
  let data = null;
  try {
    const response = await fetch(BASE_URL + "agent?port=" + port);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  const {
    agent: { balance, keys, stake },
    transaction_fee,
  } = yield call(fetchAgent, payload);

  try {
    yield put(
      getAgentSuccess({
        balance,
        keys,
        stake: formatNumber(stake),
        transactionFee: parseFloat(transaction_fee).toFixed(6),
      })
    );
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getAgent, handler);
}
