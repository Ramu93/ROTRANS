import React, { useEffect, useState } from "react";
import { connect } from "react-redux";
import { useParams } from "react-router-dom";

import "./styles.css";
import TextInput from "../../../../components/TextInput";
import FieldError from "../../../../components/FieldError";
import Button from "../../../../components/Button";
import ConfirmDialog from "../../../../components/ConfirmDialog";
import RadioButton from "../RadioButton";
import { makeTransfer } from "../../actions";
import { getBalanceState, getTransactionFee } from "../../selectors";
import { isValidHex } from "../../../../utils";

const DIALOG_MSG = {
  title: {
    confirm: "Confirm",
    insufficientBalance: "Balance",
  },
  message: {
    confirm: "Are you sure you want to make the transfer?",
    insufficientBalance: "You have insufficient balance!",
  },
};

interface TransactionCardProps {
  balance: Number;
  makeTransfer: Function;
  transactionFee: string;
}

const TransactionCard: React.FC<TransactionCardProps> = ({
  balance,
  makeTransfer,
  transactionFee,
}) => {
  //get value and recipient from URL params
  const { value, recipient, port } = useParams();

  const [transferMode, setTransferMode] = useState("recipient");
  const [transferValue, setTransferValue] = useState(value || "");
  const [toPublicKey, setToPublicKey] = useState(recipient || "");
  const [validator, setValidator] = useState("");
  const [transferValueErrorMessage, setTransferValueErrorMessage] = useState(
    value === undefined || recipient === undefined ? " " : ""
  );
  const [toPublicKeyErrorMessage, setToPublicKeyErrorMessage] = useState(
    value === undefined || recipient === undefined ? " " : ""
  );
  const [validatorErrorMessage, setValidatorErrorMessage] = useState(
    recipient === undefined ? " " : ""
  );
  const [isSubmitDisabled, setIsSubmitDisabled] = useState(
    value === undefined && recipient === undefined
  );
  const [showDialog, setShowDialog] = useState(false);
  const [noBalance, setNoBalance] = useState(false);
  const [dialogMsg, setDialogMsg] = useState({ title: "", message: "" });

  useEffect(() => {
    // error message validation check for recipient mode
    const isRecipientReqSatisfied =
      transferValueErrorMessage === "" && toPublicKeyErrorMessage === "";

    // error message validation check for delegation mode
    const isDelegateReqSatisfied =
      isRecipientReqSatisfied && validatorErrorMessage === "";

    if (
      (transferMode === "recipient" && isRecipientReqSatisfied) ||
      (transferMode === "delegate" && isDelegateReqSatisfied)
    ) {
      setIsSubmitDisabled(false);
    } else {
      setIsSubmitDisabled(true);
    }
  }, [
    transferValueErrorMessage,
    toPublicKeyErrorMessage,
    validatorErrorMessage,
  ]);

  const validateTransferValue = () => {
    if (transferValue === "") {
      setTransferValueErrorMessage("Transaction value cannot be empty!");
    } else if (parseFloat(transferValue) === 0) {
      setTransferValueErrorMessage("Transaction value cannot be 0!");
    } else {
      setTransferValueErrorMessage("");
    }
  };

  const validateToPublicKey = () => {
    if (toPublicKey === "") {
      setToPublicKeyErrorMessage("Recipient's public key cannot be empty!");
    } else if (!isValidHex(toPublicKey)) {
      setToPublicKeyErrorMessage("Recipient's public key is not valid!");
    } else {
      setToPublicKeyErrorMessage("");
    }
  };

  const validateValidator = () => {
    if (transferMode === "delegate" && validator === "") {
      setValidatorErrorMessage("Validator cannot be empty!");
    } else if (!isValidHex(validator)) {
      setValidatorErrorMessage("Validator key is not valid!");
    } else {
      setValidatorErrorMessage("");
    }
  };

  const postTransfer = () => {
    makeTransfer({
      port,
      value: transferValue,
      recipient: toPublicKey,
      mode: transferMode,
      validator,
    });
    setShowDialog(false);
  };

  const handleSubmit = () => {
    // check if the transaction value is greater than the balance
    const totalFee = parseFloat(transactionFee) * parseFloat(transferValue);
    const totalTransactionValue = parseFloat(transferValue) + totalFee;
    if (totalTransactionValue > balance) {
      setDialogMsg({
        title: DIALOG_MSG.title.insufficientBalance,
        message: DIALOG_MSG.message.insufficientBalance,
      });
      setNoBalance(true);
      setShowDialog(true);
    } else {
      // there is sufficient balance
      setDialogMsg({
        title: DIALOG_MSG.title.confirm,
        message: DIALOG_MSG.message.confirm,
      });
      setNoBalance(false);
      if (!isSubmitDisabled) {
        setShowDialog(true);
      }
    }
  };

  return (
    <>
      <div className="transaction-card">
        <RadioButton onChange={setTransferMode} />
        <br />
        <TextInput
          label="Transfer Value"
          placeholder="Enter the value..."
          type="number"
          name="transactionValue"
          value={transferValue}
          onChange={(event) => {
            const value = event.target.value;
            if (parseFloat(value) < 0) {
              setTransferValue("0");
            } else {
              setTransferValue(value);
            }
          }}
          onBlur={validateTransferValue}
          required={true}
          step="0.0001"
        />
        <FieldError
          message={transferValueErrorMessage}
          visible={transferValueErrorMessage !== ""}
        />
        <br />
        <TextInput
          label="To"
          placeholder="Enter recipient's public key..."
          value={toPublicKey}
          onChange={(event) => setToPublicKey(event.target.value)}
          onBlur={validateToPublicKey}
          required={true}
          name="toPublicKey"
        />
        <FieldError
          message={toPublicKeyErrorMessage}
          visible={toPublicKeyErrorMessage !== ""}
        />
        <br />
        {transferMode === "delegate" && (
          <>
            <TextInput
              label="Validator"
              placeholder="Enter validator public key..."
              value={validator}
              onChange={(event) => setValidator(event.target.value)}
              required={true}
              onBlur={validateValidator}
              name="validator"
            />
            <FieldError
              message={validatorErrorMessage}
              visible={validatorErrorMessage !== ""}
            />
            <br />
          </>
        )}
        <Button
          label="Transfer"
          onClick={handleSubmit}
          disabled={isSubmitDisabled}
          icon={<img src={require("../../../../assets/svg/go.svg")} />}
        />
      </div>
      <ConfirmDialog
        visible={showDialog}
        title={dialogMsg.title}
        message={dialogMsg.message}
        handleAgree={noBalance ? undefined : postTransfer}
        handleDisagree={() => setShowDialog(false)}
        showOk={noBalance}
        handleOk={() => setShowDialog(false)}
      />
    </>
  );
};

const mapDispatchToProps = {
  makeTransfer,
};

const mapStateToProps = (state) => ({
  balance: getBalanceState(state),
  transactionFee: getTransactionFee(state),
});

export default connect(mapStateToProps, mapDispatchToProps)(TransactionCard);
