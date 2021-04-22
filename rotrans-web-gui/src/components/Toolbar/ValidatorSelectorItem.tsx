import React from "react";

export interface ValidatorSelectItemProps {
  agentName: string;
  agentIp: string;
  isSelected?: boolean;
  onClick?:
    | ((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => void)
    | undefined;
}

const ValidatorSelectItem: React.FC<ValidatorSelectItemProps> = ({
  agentName,
  agentIp,
  isSelected,
  onClick,
}) => (
  <div
    className="toolbar-profile-component"
    onClick={onClick}
  >
    <div className="toolbar-image-div">
      <div className="toolbar-avatar"></div>
    </div>
    <div className="toolbar-name-div">
      <span data-testid="toolbarSelectedAgentName" className="toolbar-name">{agentName}</span>
      <span data-testid="toolbarSelectedAgentIp" className="toolbar-ip">{agentIp}</span>
    </div>
    <div className="toolbar-icon-div">
      {isSelected && (
        <img className="icon" src={require("../../assets/svg/down.svg")} />
      )}
    </div>
  </div>
);

export default ValidatorSelectItem;
