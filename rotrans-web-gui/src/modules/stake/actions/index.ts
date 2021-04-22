import { createAction } from "redux-actions";

// saga actions
export const getStakeDist = createAction("@@saga/GET_STAKE_DIST");

// state actions
export const getStakeDistSuccess = createAction(
  "@@state/GET_STAKE_DIST_SUCCESS"
);
