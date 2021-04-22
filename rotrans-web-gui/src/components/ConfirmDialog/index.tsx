import React from "react";
import Button from "@material-ui/core/Button";
import Dialog from "@material-ui/core/Dialog";
import DialogActions from "@material-ui/core/DialogActions";
import DialogContent from "@material-ui/core/DialogContent";
import DialogContentText from "@material-ui/core/DialogContentText";
import DialogTitle from "@material-ui/core/DialogTitle";

interface DialogProps {
  visible: boolean;
  title: string;
  message: string;
  handleAgree: any;
  handleDisagree: any;
  onClose?:
    | ((event: {}, reason: "backdropClick" | "escapeKeyDown") => void)
    | undefined;
  showOk: boolean;
  handleOk: any;
}

const AlertDialog: React.FC<DialogProps> = ({
  visible,
  title,
  message,
  handleAgree,
  handleDisagree,
  onClose,
  showOk,
  handleOk,
}) => {
  return (
    <Dialog
      open={visible}
      onClose={onClose}
      aria-labelledby="alert-dialog-title"
      aria-describedby="alert-dialog-description"
    >
      <DialogTitle id="alert-dialog-title">{title}</DialogTitle>
      <DialogContent>
        <DialogContentText id="alert-dialog-description">
          {message}
        </DialogContentText>
      </DialogContent>
      {!showOk && (
        <DialogActions>
          <Button onClick={handleDisagree} color="primary">
            No
          </Button>
          <Button onClick={handleAgree} color="primary" autoFocus>
            Yes
          </Button>
        </DialogActions>
      )}
      {showOk && (
        <DialogActions>
          <Button onClick={handleOk} color="primary">
            Okay
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
};

export default AlertDialog;
