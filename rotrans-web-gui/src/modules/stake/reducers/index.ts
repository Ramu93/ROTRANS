import { handleActions } from "redux-actions";

import { getStakeDist, getStakeDistSuccess } from "../actions";

const initialState = {
  isLoading: false,
  stakeDist: [],
};

const stakeDistReducer = handleActions(
  {
    [getStakeDist]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [getStakeDistSuccess]: (state, { payload }) => ({
      ...state,
      isLoading: false,
      stakeDist: payload.stakeDist,
    }),
  },
  initialState
);

export default stakeDistReducer;
