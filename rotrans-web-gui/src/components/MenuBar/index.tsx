import React from "react";
import { Link, useLocation } from "react-router-dom";
import "./styles.css";

interface Props {
  port: string;
}

const MenuBar: React.FC<Props> = ({ port }) => {
  let activeMenu = 0;
  const location = useLocation();
  if (location.pathname.includes("visualization")) {
    activeMenu = 1;
  } else if (location.pathname.includes("transactions")) {
    activeMenu = 2;
  } else {
    activeMenu = 3;
  }

  return (
    <div className="menubar">
      <div className="menu menu-no-pointer">
        <img src={require("../../assets/svg/coin.svg")} />
      </div>
      <Link to={`/${port}/visualization`}>
        <div
          data-testid="vizMenuItem"
          className={activeMenu === 1 ? "menu menu-active" : "menu"}
        >
          <img src={require("../../assets/svg/board.svg")} />
        </div>
      </Link>
      <Link to={`/${port}/transactions`}>
        <div
          data-testid="transactionsMenuItem"
          className={activeMenu === 2 ? "menu menu-active" : "menu"}
        >
          <img src={require("../../assets/svg/rocket.svg")} />
        </div>
      </Link>
      <Link to={`/${port}/stake`}>
        <div
          data-testid="stakeMenuItem"
          className={activeMenu === 3 ? "menu menu-active" : "menu"}
        >
          <img
            src={require("../../assets/stake.png")}
            style={{ height: 30, width: 30 }}
          />
        </div>
      </Link>
    </div>
  );
};

export default MenuBar;
