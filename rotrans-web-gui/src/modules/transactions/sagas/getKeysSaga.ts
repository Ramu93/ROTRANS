import { call, put, takeEvery } from 'redux-saga/effects';
import { getKeys, getKeysSuccess } from '../actions';

import { key } from '../../../fixtures/constants';

function* handler({ payload }) {
  try {
    yield put(getKeysSuccess({
      publicKey: key,
      secretKey: key,
    }));
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getKeys, handler);
}
