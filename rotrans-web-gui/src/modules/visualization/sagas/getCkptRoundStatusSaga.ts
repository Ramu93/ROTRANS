import { call, put, takeEvery } from "redux-saga/effects";
import { getCkptRoundStatus, getCkptRoundStatusSuccess } from "../actions";

import { BASE_URL } from "../../../utils";

async function fetchRoundStatus(port) {
  let data = null;
  try {
    const response = await fetch(BASE_URL + "round_status?port=" + port);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const { round_status } = yield call(fetchRoundStatus, payload.port);
    yield put(
      getCkptRoundStatusSuccess({
        round_status,
      })
    );
    
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getCkptRoundStatus, handler);
}
