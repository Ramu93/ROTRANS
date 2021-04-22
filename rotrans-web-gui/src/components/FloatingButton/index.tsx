import React from "react";

import "./styles.css";

interface FloatingButtonProps {
  icon: any;
  handleClick:
    | ((event: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => void)
    | undefined;
}

const FloatingButton: React.FC<FloatingButtonProps> = ({
  icon,
  handleClick,
}) => {
  return (
    <a
      data-testid="floatingActionBtn"
      href="#"
      className="float"
      onClick={handleClick}
    >
      {icon}
    </a>
  );
};

export default FloatingButton;
