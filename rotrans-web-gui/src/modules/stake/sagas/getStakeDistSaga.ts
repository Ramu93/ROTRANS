import { call, put, takeEvery } from "redux-saga/effects";
import { BASE_URL } from "../../../utils";
import { getStakeDist, getStakeDistSuccess } from "../actions";

async function fetchAgent({ port }) {
  let data = null;
  try {
    const response = await fetch(BASE_URL + "stake_dist?port=" + port);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  const data = yield call(fetchAgent, payload);
  try {
    yield put(
      getStakeDistSuccess({
        stakeDist: data,
      })
    );
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getStakeDist, handler);
}
