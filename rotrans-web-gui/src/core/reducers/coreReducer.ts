import { handleActions } from 'redux-actions';

import { getValidators, getValidatorsSuccess, setRootValidator } from '../actions';

const initialState = {
  isLoading: false,
  validators: [],
};

const coreReducer = handleActions({
  [getValidators]: (state) => ({
    ...state,
    isLoading: true,
  }),
  [getValidatorsSuccess]: (state, { payload }) => ({
    ...state,
    isLoading: false,
    validators: payload.validators,
  }),
  [setRootValidator]: (state, { payload }) => ({
    ...state,
    rootValidator: payload,
  })
}, initialState);

export default coreReducer;