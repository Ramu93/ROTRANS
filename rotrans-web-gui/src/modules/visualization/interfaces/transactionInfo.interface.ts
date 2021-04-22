import { Wallet } from "./wallet.interface";

export interface TransactionInfo {
  total_inputs: string;
  total_outputs: string;
  total_fees: string;
  stake: string;
  inputs: [Wallet];
  outputs: [Wallet];
}