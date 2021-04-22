import { call, put, takeEvery } from 'redux-saga/effects';
import { getBalance, getBalanceSuccess } from '../actions';

function* handler({ payload }) {
  try {
    yield put(getBalanceSuccess({
      balance: '3,200',
    }));
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getBalance, handler);
}
