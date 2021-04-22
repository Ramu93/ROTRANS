import React from "react";
import Spinner from "react-spinner-material";

import './styles.css';

interface Props {
  visible: boolean;
}

const Loader: React.FC<Props> = ({ visible }) => (
  <div data-testid="spinner" className="custom-loader-div">
    <Spinner radius={80} color={"#6435c9"} stroke={5} visible={visible} />
  </div>
);

export default Loader;
