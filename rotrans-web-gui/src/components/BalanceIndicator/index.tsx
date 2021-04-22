import React from "react";
import "./styles.css";

interface Props {
  balance: string;
}

const BalanceIndicator: React.FC<Props> = ({ balance }) => {
  return (
    <>
      <span className="value-label">Available Balance</span>
      <span data-testid="balanceIndicatorValueText" className="value-text">{balance}</span>
    </>
  );
};

export default BalanceIndicator;
