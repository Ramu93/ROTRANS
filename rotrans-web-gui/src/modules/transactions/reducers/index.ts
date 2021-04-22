import { handleActions } from "redux-actions";

import {
  getKeys,
  getKeysSuccess,
  getBalance,
  getBalanceSuccess,
  makeTransfer,
  getAgent,
  getAgentSuccess,
  generateKeyPair,
} from "../actions";

const initialState = {
  isLoading: false,
  keys: [],
  balance: "",
  stake: "",
  transactionFee: 0,
};

const transactionsReducer = handleActions(
  {
    [getKeys]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [getKeysSuccess]: (state, { payload }) => ({
      ...state,
      isLoading: false,
      keys: payload.keys,
    }),
    [getBalance]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [getBalanceSuccess]: (state, { payload }) => ({
      ...state,
      isLoading: false,
      balance: payload.balance,
    }),
    [getAgent]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [getAgentSuccess]: (state, { payload }) => ({
      ...state,
      isLoading: false,
      keys: payload.keys,
      balance: payload.balance,
      stake: payload.stake,
      transactionFee: payload.transactionFee,
    }),
    [makeTransfer]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [generateKeyPair]: (state) => ({
      ...state,
      isLoading: true,
    }),
  },
  initialState
);

export default transactionsReducer;
