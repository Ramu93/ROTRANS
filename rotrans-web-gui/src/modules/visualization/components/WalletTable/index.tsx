import React from "react";
import { Wallet } from "../../interfaces/wallet.interface";
import "./styles.css";

interface WalletTableProps {
  wallets: [Wallet] | undefined;
}

const WalletTable: React.FC<WalletTableProps> = ({ wallets }) => {
  return (
    <div className="table-container">
      <table className="custom-table">
        {wallets &&
          wallets.map((wallet) => (
            <tr>
              <td>{wallet.public_key}</td>
              <td>{parseFloat(wallet.value)}</td>
            </tr>
          ))}
      </table>
    </div>
  );
};

export default WalletTable;
