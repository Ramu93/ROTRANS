import React, { useEffect } from "react";
import { connect } from "react-redux";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { getCkptRoundStatusState } from "../../selectors";
import { getCkptRoundStatus } from "../../actions";

import "./styles.css";
import { determineRoundStatus } from "../../../../utils";

interface CkptRoundStatusProps {
  roundStatus: number;
  getCkptRoundStatus: Function;
}

const CkptRoundStatus: React.FC<CkptRoundStatusProps> = ({
  roundStatus,
  getCkptRoundStatus,
}) => {
  const { port } = useParams();
  useEffect(() => {
    const interval = setInterval(() => {
      getCkptRoundStatus({ port });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (roundStatus !== 0) {
      toast.dark(`${determineRoundStatus(roundStatus)} in progress`, {
        toastId: 1,
        position: "top-right",
        autoClose: 2000,
        hideProgressBar: true,
        closeOnClick: true,
        pauseOnHover: false,
        draggable: false,
        progress: 0,
      });
    }
  }, [roundStatus]);

  return (
    <div className="ckpt-status-message">
      <span className="ckpt-status-title">Checkpoint Round Status: </span>
      <span>
        {roundStatus === 0
          ? "Unknown"
          : `${determineRoundStatus(roundStatus)} in progress`}
      </span>
    </div>
  );
};

const mapStateToProps = (state) => ({
  roundStatus: getCkptRoundStatusState(state),
});

const mapDispatchToProps = {
  getCkptRoundStatus,
};

export default connect(mapStateToProps, mapDispatchToProps)(CkptRoundStatus);
