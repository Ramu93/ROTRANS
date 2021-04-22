import { call, put, takeEvery } from "redux-saga/effects";
import { toast } from "react-toastify";

import { BASE_URL, formatNumber } from "../../../utils";
import { makeTransfer, getAgentSuccess } from "../actions";

async function postTransaction(payload) {
  const { value, recipient, mode, validator } = payload;
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value, recipient, mode, validator }),
  };
  let data = null;
  try {
    const response = await fetch(
      BASE_URL + "transfer?port=" + payload.port,
      options
    );
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const {
      agent: { balance, keys, stake },
    } = yield call(() => postTransaction(payload));
    toast.dark("Transaction has been submitted!", {
      toastId: 1,
      position: "bottom-center",
      autoClose: 5000,
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: false,
      draggable: false,
      progress: 0,
    });
    yield put(
      getAgentSuccess({
        balance: formatNumber(balance),
        keys,
        stake: formatNumber(stake),
      })
    );
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(makeTransfer, handler);
}
