import { call, put, takeEvery } from 'redux-saga/effects';
import validators from '../../fixtures/validators';
import { getValidators, getValidatorsSuccess } from '../actions';

function* handler({ payload }) {
  try {
    yield put(getValidatorsSuccess({
      validators: validators
    }));
  } catch (e) {
    console.log(e);
  }
}

export default function* saga() {
  yield takeEvery(getValidators, handler);
}
