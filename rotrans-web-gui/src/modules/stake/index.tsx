import React, { useState, useEffect } from "react";
import { connect } from "react-redux";
import { Helmet } from "react-helmet";
import { useParams } from "react-router-dom";

import Loader from "../../components/Loader";
import MenuBar from "../../components/MenuBar";
import { getStakeDistState, getLoadingState } from "./selectors";
import { getStakeDist } from "./actions";

import "./styles.css";
import StakeTable from "./components/StakeDistTable";

const Stake = ({ isLoading, getStakeDist, stakeDist }) => {
  const { port } = useParams();

  useEffect(() => {
    getStakeDist({ port });
  }, []);

  return (
    <>
      <Helmet>
        <title>{port + " ROTRANS - Stake Distribution"}</title>
      </Helmet>
      <div className="container">
        <MenuBar port={port} />
        <div className="workspace stake-workspace">
          {!isLoading && (
            <div className="stake-dist-card">
              <StakeTable stakeDist={stakeDist} />
            </div>
          )}
          <Loader visible={isLoading} />
        </div>
      </div>
    </>
  );
};

const mapStateToProps = (state) => ({
  stakeDist: getStakeDistState(state),
  isLoading: getLoadingState(state),
});

const mapDispatchToProps = {
  getStakeDist,
};

export default connect(mapStateToProps, mapDispatchToProps)(Stake);
