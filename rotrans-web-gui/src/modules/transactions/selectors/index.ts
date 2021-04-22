export const getLoadingState = (state) => state.transactionsReducer.isLoading;

export const getBalanceState = (state) =>
  parseFloat(state.transactionsReducer.balance);

export const getKeysState = (state) => state.transactionsReducer.keys;

export const getTransactionFee = (state) =>
  state.transactionsReducer.transactionFee;
