import { createSelector } from "reselect";
import { find, get } from "lodash";

export const getSelectedNodeId = (state) => state.vizReducer.selectedNodeId;

export const getLoadingState = (state) => state.vizReducer.isLoading;

const getDagStateRaw = (state) => state.vizReducer.dag;

// export const getDagState = state => createSelector(getDagStateRaw, dag => {
//   return state.vizReducer.dag;
// });
// replace this function with the above one and modify it when the DAG data structure is ready
export const getDagState = (state) => state.vizReducer.dag;

export const getSelectedNode = createSelector(
  getSelectedNodeId,
  getDagStateRaw,
  (nodeId, dag) => find(get(dag, "nodes", []), (node) => node.id === nodeId)
);

export const getTransactionInfoState = (state) =>
  state.vizReducer.transactionInfo;

export const getIsDetailsFirstLoad = (state) =>
  state.vizReducer.isNodeDetailsFirstLoad;

export const getCkptRoundStatusState = (state) => state.vizReducer.roundStatus;
