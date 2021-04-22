import { Wallet } from "./wallet.interface";

export interface Node {
  id: string;
  symbolType: SymbolType;
  label: string;
  meta: Meta;
}

interface Meta {
  isTransaction: Boolean;
  isCheckpoint: Boolean;
  origin: string;
  total_inputs?: string;
  total_outputs?: string;
  total_fees?: string;
  isConfirmed: Boolean;
  inputs?: [Wallet];
  outputs?: [Wallet];
  nutxo?: number;
  lock_time?: string;
  miner?: string; 
  height?: number;
  ack_length?: number;
  total_stake?: string;
}

export enum SymbolType {
  SQUARE = "square",
  CIRCLE = "circle",
}
