import React from "react";
import "./styles.css";

interface Props {
  label?: string;
  icon?: any;
  disabled?: boolean;
  onClick?:
    | ((event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void)
    | undefined;
  iconButton?: boolean;
}

const Button: React.FC<Props> = ({ label, icon, onClick, disabled, iconButton }) => {
  return (
    <div className="custom-btn-div">
      <div className="custom-btn-inner-div">
        <button className="custom-btn" onClick={onClick} disabled={disabled}>
          {label && (
            <div className="txt-btn-div">
              <span data-testid="label" className="btn-label">
                {" "}
                {label}
              </span>
            </div>
          )}
          {icon && (
            <div className="icon-btn-div">
              <span data-testid="icon" className="btn-icon">
                {icon}
              </span>
            </div>
          )}
        </button>
      </div>
    </div>
  );
};

export default Button;
