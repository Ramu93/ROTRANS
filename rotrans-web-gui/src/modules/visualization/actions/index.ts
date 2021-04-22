import { createAction } from "redux-actions";

// saga actions
export const getDag = createAction("@@saga/GET_DAG");
export const getTransactionInfo = createAction("@@saga/GET_TRANSACTION_INFO");
export const getCkptRoundStatus = createAction("@@saga/GET_CKPT_ROUND_STATUS");

// state actions
export const setSelectedNode = createAction("@@state/SET_SELECTED_NODE");
export const getDagSuccess = createAction("@@state/GET_DAG_SUCCESS");
export const getTransactionInfoSuccess = createAction(
  "@@state/GET_TRANSACTION_INFO_SUCCESS"
);
export const getCkptRoundStatusSuccess = createAction(
  "@@state/GET_CKPT_ROUND_STATUS_SUCCESS"
);
