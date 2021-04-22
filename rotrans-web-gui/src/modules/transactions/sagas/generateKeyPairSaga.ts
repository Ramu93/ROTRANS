import { call, put, takeEvery } from "redux-saga/effects";
import { toast } from "react-toastify";

import { BASE_URL, formatNumber } from "../../../utils";
import { generateKeyPair, getAgentSuccess } from "../actions";

async function postGenerateKeyPair({ port }) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // body: JSON.stringify(),
  };
  let data = null;
  try {
    const response = await fetch(BASE_URL + "keys?port=" + port, options);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const { balance, keys, stake } = yield call(() =>
      postGenerateKeyPair(payload)
    );
    toast.dark("Key pair generated!", {
      toastId: 1,
      position: "bottom-center",
      autoClose: 4000,
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
  yield takeEvery(generateKeyPair, handler);
}
