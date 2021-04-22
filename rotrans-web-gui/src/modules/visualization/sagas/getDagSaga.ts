import { call, put, takeEvery } from "redux-saga/effects";
import { getDag, getDagSuccess } from "../actions";

import { BASE_URL } from "../../../utils";

async function fetchDag(port) {
  let data = null;
  try {
    const response = await fetch(BASE_URL + "dag?port=" + port);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const { dag, round_status } = yield call(fetchDag, payload.port);
    yield put(
      getDagSuccess({
        dag,
        round_status,
      })
    );
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getDag, handler);
}
