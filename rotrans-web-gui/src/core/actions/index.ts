import { createAction } from 'redux-actions';

// saga actions
export const getValidators = createAction('@@saga/GET_VALIDATORS');

// state actions
export const getValidatorsSuccess = createAction('@@state/GET_VALIDATORS_SUCCESS');
export const setRootValidator = createAction('@@state/SET_ROOT_VALIDATOR');