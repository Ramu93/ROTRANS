import { createAction } from "redux-actions";

// saga actions
export const getKeys = createAction("@@saga/GET_KEYS");
export const getBalance = createAction("@@saga/GET_BALANCE");
export const makeTransfer = createAction("@@saga/MAKE_TRANSFER");
export const getAgent = createAction("@@saga/GET_AGENT");
export const generateKeyPair = createAction("@@saga/GENERATE_KEY_PAIR");
export const addKey = createAction("@@saga/ADD_KEY");

// state actions
export const getKeysSuccess = createAction("@@state/GET_KEYS_SUCCESS");
export const getBalanceSuccess = createAction("@@state/GET_BALANCE_SUCCESS");
export const getAgentSuccess = createAction("@@state/GET_AGENT_SUCCESS");
export const addKeySuccess = createAction("@@state/ADD_KEY_SUCCESS");
