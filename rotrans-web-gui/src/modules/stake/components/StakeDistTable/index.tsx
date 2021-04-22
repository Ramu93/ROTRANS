import React from "react";
import { StakeDist } from "../../interfaces/stake-dist.interface.dto";
import "./styles.css";

interface StakeTableProps {
  stakeDist: [StakeDist];
}

const StakeTable: React.FC<StakeTableProps> = ({ stakeDist }) => {
  return (
    <div className="stake-table-container">
      <table className="stake-table">
        <tr>
          <th>Public Key</th>
          <th>Stake</th>
          <th>Stake Percentage</th>
        </tr>
        {stakeDist &&
          stakeDist.map((stake) => (
            <tr>
              <td>{stake.public_key}</td>
              <td>{stake.stake_t}</td>
              <td>{stake.stake_p}</td>
            </tr>
          ))}
      </table>
    </div>
  );
};

export default StakeTable;
