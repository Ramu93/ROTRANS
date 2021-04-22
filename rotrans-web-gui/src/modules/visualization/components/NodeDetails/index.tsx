import React, { useEffect, useState } from "react";
import { connect } from "react-redux";
import { get } from "lodash";
import Button from "@material-ui/core/Button";
import Dialog from "@material-ui/core/Dialog";
import DialogActions from "@material-ui/core/DialogActions";
import DialogContent from "@material-ui/core/DialogContent";
import DialogContentText from "@material-ui/core/DialogContentText";
import DialogTitle from "@material-ui/core/DialogTitle";
import { useParams } from "react-router-dom";

import { getSelectedNode, getTransactionInfoState } from "../../selectors";
import { getTransactionInfo, setSelectedNode } from "../../actions";
import { Node } from "../../interfaces/node.interface";
import { TransactionInfo } from "../../interfaces/transactionInfo.interface";
import WalletTable from "../WalletTable";
import { timestampToUTC } from "../../../../utils";

interface NodeDetailsProps {
  node: Node;
  getTransactionInfo: Function;
  transactionInfo: TransactionInfo;
  setSelectedNode: Function;
}

const NodeDetails: React.FC<NodeDetailsProps> = ({
  node,
  getTransactionInfo,
  transactionInfo,
  setSelectedNode,
}) => {
  const [visible, setVisible] = useState(false);
  const { port } = useParams();

  const meta = node && node.meta;

  const isTransaction = node && node.meta.isTransaction;
  const isCheckpoint = node && node.meta.isCheckpoint;
  const isConfirmed = isTransaction && get(meta, "isConfirmed", false);

  const title = isCheckpoint
    ? "Checkpoint Details"
    : isTransaction
    ? "Transaction Details"
    : "Ack Details";

  useEffect(() => setVisible(true), [node]);

  const handleClose = () => {
    setVisible(false);
    setSelectedNode(null);
  };

  const content = (label, value) => (
    <DialogContentText id="alert-dialog-description">
      <div data-testid="nodeDetailsContent">
        <label>{label}</label>
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        {value}
      </div>
    </DialogContentText>
  );

  const getStatusText = (isConfirmed) => {
    if (isConfirmed) {
      return <span style={{ color: "green" }}>Confirmed</span>;
    }
    return <span style={{ color: "red" }}>Pending</span>;
  };

  const getTransactionTotalInputs = (isConfirmed) => {
    let totalInputs: string;
    totalInputs = get(node.meta, "total_inputs", "");
    if (!isConfirmed) {
      totalInputs = transactionInfo.total_inputs;
    }
    return parseFloat(totalInputs);
  };

  const getTransactionTotalOutputs = (isConfirmed) => {
    let totalOutputs: string;
    totalOutputs = get(node.meta, "total_outputs", "");
    if (!isConfirmed) {
      totalOutputs = transactionInfo.total_outputs;
    }
    return parseFloat(totalOutputs);
  };

  const getTransactionFees = (isConfirmed) => {
    let totalFees: string;
    totalFees = get(node.meta, "total_fees", "");
    if (!isConfirmed) {
      totalFees = transactionInfo.total_fees;
    }
    if (totalFees !== "NA") {
      return parseFloat(totalFees);
    }
    return totalFees;
  };

  const getTransactionInputs = (isConfirmed) => {
    if (!isConfirmed) {
      return transactionInfo.inputs;
    }
    return node.meta.inputs;
  };

  const getTransactionOutputs = (isConfirmed) => {
    if (!isConfirmed) {
      return transactionInfo.outputs;
    }
    return node.meta.outputs;
  };

  const getNoOfUnspentOutputs = () => node.meta.nutxo;

  const getHeight = () => node.meta.height;

  const getMiner = () => node.meta.miner;

  const getTimeStamp = () =>
    node.meta.lock_time && timestampToUTC(parseFloat(node.meta.lock_time));

  const getTotalStake = () => node.meta.total_stake;

  useEffect(() => {
    if (node) {
      const isConfirmed = isTransaction && get(meta, "isConfirmed", false);
      if (!isConfirmed) {
        getTransactionInfo({ transactionId: node.id, port });
      }
    }
  }, [node]);

  return (
    <Dialog
      open={node && visible}
      aria-labelledby="alert-dialog-title"
      aria-describedby="alert-dialog-description"
      maxWidth="md"
      fullWidth
      onEscapeKeyDown={handleClose}
    >
      <DialogTitle id="alert-dialog-title">{title}</DialogTitle>
      <DialogContent>
        {node && content("Identifier", get(node, "id", ""))}
        {isTransaction && !isCheckpoint && (
          <>
            {content("Total Inputs", getTransactionTotalInputs(isConfirmed))}
            <WalletTable wallets={getTransactionInputs(isConfirmed)} />
            {content("Total Outputs", getTransactionTotalOutputs(isConfirmed))}
            <WalletTable wallets={getTransactionOutputs(isConfirmed)} />
            {content("Total Fees", getTransactionFees(isConfirmed))}
            {!isConfirmed &&
              content("Stake", get(transactionInfo, "stake", ""))}
            {content("Status", getStatusText(isConfirmed))}
          </>
        )}
        {isCheckpoint && (
          <>
            {content("Miner", getMiner())}
            {content("UTC Time", getTimeStamp())}
            {content("Total Stake", getTotalStake())}
            {content("Height", getHeight())}
            {content("No. of UTXO", getNoOfUnspentOutputs())}
            {content(
              "Total Unspent Outputs",
              getTransactionTotalInputs(isConfirmed)
            )}
            <WalletTable wallets={getTransactionInputs(isConfirmed)} />
            {content("Fee Rewards", getTransactionTotalOutputs(isConfirmed))}
            <WalletTable wallets={getTransactionOutputs(isConfirmed)} />
          </>
        )}
        {!isTransaction && (
          <>
            {content("Previous", get(meta, "prev_ack", "Unknown"))}
            {content("Transaction", get(meta, "txn_id", "Unknown"))}
            {content("Validator", get(meta, "validator", "Unknown"))}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} color="primary">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

const mapStateToProps = (state) => ({
  node: getSelectedNode(state),
  transactionInfo: getTransactionInfoState(state),
});

const mapDispatchToProps = {
  getTransactionInfo,
  setSelectedNode,
};

export default connect(mapStateToProps, mapDispatchToProps)(NodeDetails);
