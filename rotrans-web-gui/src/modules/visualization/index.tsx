import React, { useEffect } from "react";
import { connect } from "react-redux";
import { isEmpty } from "lodash";
import { Helmet } from "react-helmet";
import { useParams } from "react-router-dom";

import Viz from "./components/Viz";
import NodeDetails from "./components/NodeDetails";
import Loader from "../../components/Loader";
import { getDag } from "./actions";
import { getLoadingState, getDagState } from "./selectors";
import MenuBar from "../../components/MenuBar";
import CkptRoundStatus from "./components/CkptRoundStatus";

const Visualization = ({ isLoading, rootValidator, getDag, dag }) => {
  const { port } = useParams();

  useEffect(() => {
    if (isEmpty(dag)) {
      fetchData(port);
    }
  }, []);

  const fetchData = (port) => {
    // pass validator id and get data here
    console.log("*******************", "fetch dag again");
    getDag({ port });
  };

  return (
    <>
      <Helmet>
        <title>{port + " ROTRANS - Visualization"}</title>
      </Helmet>
      <div className="container">
        <MenuBar port={port} />
        <div className="workspace">
          {!isLoading && !isEmpty(dag) && (
            <Viz graphData={dag} onReload={() => fetchData(port)} />
          )}
          <NodeDetails />
          <CkptRoundStatus />
          <Loader visible={isLoading} />
        </div>
      </div>
    </>
  );
};

const mapStateToProps = (state) => ({
  isLoading: getLoadingState(state),
  dag: getDagState(state),
});

const mapDispatchToProps = {
  getDag,
};

export default connect(mapStateToProps, mapDispatchToProps)(Visualization);
