import { call, put, takeEvery } from "redux-saga/effects";
import { toast } from "react-toastify";

import { BASE_URL } from "../../../utils";
import { addKey, addKeySuccess } from "../actions";

async function postNewKey({ key, port }) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  };
  let data = null;
  try {
    const response = await fetch(BASE_URL + "addKey?port=" + port, options);
    data = await response.json();
  } catch (err) {
    console.error(err);
  }
  return data;
}

function* handler({ payload }) {
  try {
    const response = yield call(() => postNewKey(payload));
    toast.dark("Added new key!", {
      toastId: 1,
      position: "bottom-center",
      autoClose: 5000,
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: false,
      draggable: false,
      progress: 0,
    });
    console.log(response);
    yield put(addKeySuccess());
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(addKey, handler);
}
