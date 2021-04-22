import { combineReducers } from 'redux';

import coreReducer from './coreReducer';
import vizReducer from '../../modules/visualization/reducers';
import transactionsReducer from '../../modules/transactions/reducers';
import stakeDistReducer from '../../modules/stake/reducers';

export default combineReducers({
  coreReducer,
  vizReducer,
  transactionsReducer,
  stakeDistReducer,
});