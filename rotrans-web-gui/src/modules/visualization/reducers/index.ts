import { handleActions } from "redux-actions";

import {
  getDag,
  getDagSuccess,
  getTransactionInfoSuccess,
  setSelectedNode,
  getCkptRoundStatus,
  getCkptRoundStatusSuccess,
} from "../actions";

const initialState = {
  isLoading: false,
  selectedNodeId: "",
  dag: {},
  transactionInfo: {},
  isNodeDetailsFirstLoad: true,
  roundStatus: 0,
};

const vizReducer = handleActions(
  {
    [getDag]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [getDagSuccess]: (state, { payload }) => ({
      ...state,
      isLoading: false,
      dag: payload.dag,
      roundStatus: payload.round_status,
    }),
    [setSelectedNode]: (state, { payload }) => ({
      ...state,
      selectedNodeId: payload,
    }),
    [getTransactionInfoSuccess]: (state, { payload }) => ({
      ...state,
      transactionInfo: payload.transactionInfo,
    }),
    [getCkptRoundStatus]: (state) => ({
      ...state,
    }),
    [getCkptRoundStatusSuccess]: (state, { payload }) => ({
      ...state,
      roundStatus: payload.round_status,
    }),
  },
  initialState
);

export default vizReducer;
