import React, { useState, useEffect } from "react";
import { Graph } from "react-d3-graph";

const graphConfig = {
  nodeHighlightBehavior: true,
  directed: true,
  minZoom: 0.3,
  maxZoom: 4,
  initialZoom: 0.5,
  // width: 2000,
  panAndZoom: false,
  // staticGraph: true,
  automaticRearrangeAfterDropNode: true,
  focusAnimationDuration: 0,
  node: {
    color: "lightgreen",
    size: 1000,
    highlightStrokeColor: "blue",
    mouseCursor: "pointer",
    fontSize: 12,
    fontWeight: "normal",
    highlightFontSize: 14,
    highlightFontWeight: "bold",
    labelPosition: "top",
    labelProperty: "label",
  },
  link: {
    color: "#d3d3d3",
    fontColor: "black",
    fontSize: 8,
    fontWeight: "normal",
    highlightColor: "red",
    highlightFontSize: 8,
    highlightFontWeight: "normal",
    labelProperty: "label",
    mouseCursor: "pointer",
    opacity: 1,
    renderLabel: false,
    semanticStrokeWidth: false,
    strokeWidth: 1.5,
    markerHeight: 6,
    markerWidth: 6,
  },
  d3: {
    alphaTarget: 0.05,
    gravity: -200,
    linkLength: 200,
    linkStrength: 1,
    disableLinkForce: false,
  },
};

const CustomGraph = ({ data, onClickNode }) => {
  const [config, setConfig] = useState(graphConfig);

  return (
    <>
      <Graph
        id="dag-viz"
        data={data}
        config={config}
        onClickNode={onClickNode}
      />
    </>
  );
};

export default CustomGraph;
