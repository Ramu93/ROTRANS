import React from "react";

import Button from "../Button";
import "./styles.css";

interface ModelProps {
  show: boolean;
  children: any;
  confirmLabel?: string;
  handleConfirm?:
    | ((event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void)
    | undefined;
  handleClose:
    | ((event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void)
    | undefined;
}

const Modal: React.FC<ModelProps> = ({
  handleClose,
  show,
  children,
  confirmLabel,
  handleConfirm,
}) => {
  const showHideClassName = show ? "modal display-block" : "modal display-none";

  return (
    <div className={showHideClassName} data-testid="modalMain">
      <section className="modal-main">
        <div className="modal-content">
          <div className="modal-children">{children}</div>
          <div className="modal-actions">
            {confirmLabel && (
              <button data-testid="modalActionBtn" className="modal-btn" onClick={handleConfirm}>
                <span className="btn-label">{confirmLabel}</span>
              </button>
            )}
            <button
              data-testid="modalCloseBtn"
              className="modal-btn"
              onClick={handleClose}
            >
              <span className="btn-label">Close</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Modal;
