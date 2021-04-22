import React from "react";
import { useDispatch } from "react-redux";

import "./styles.css";
import Graph from "../../../../components/Graph/";
import ToolBar from "../../../../components/Toolbar/index";
import { setSelectedNode } from "../../actions";
import Button from "../../../../components/Button";
import { Node } from "../../interfaces/node.interface";
import { Link } from "../../interfaces/link.interface";

interface Props {
  graphData: {
    nodes: [Node];
    links: [Link];
  };
  onReload: Function;
}

const Viz: React.FC<Props> = ({ graphData, onReload }) => {
  const dispatch = useDispatch();

  return (
    <div className="card">
      <ToolBar
        title="Visualization"
        component={
          <div className="reload-viz-btn">
            <Button
              iconButton
              icon={
                <img
                  src={require("../../../../assets/svg/refresh.svg")}
                  className="viz-reload-icon"
                />
              }
              onClick={() => onReload()}
            />
          </div>
        }
      />
      <div className="segment-viz">
        {graphData.nodes.length > 0 && (
          <Graph
            data={graphData}
            onClickNode={(selectedNodeId) =>
              dispatch(setSelectedNode(selectedNodeId))
            }
          />
        )}
      </div>
    </div>
  );
};

export default Viz;
