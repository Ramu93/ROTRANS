import React from "react";
import "./styles.css";

interface Props {
  message: string;
  visible: boolean;
}

const FieldError: React.FC<Props> = ({ message, visible }) => (
  <span className="custom-field-error">{visible ? message : ""}</span>
);

export default FieldError;
