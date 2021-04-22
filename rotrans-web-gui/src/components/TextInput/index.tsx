import React from "react";
import "./styles.css";

interface Props {
  ref?: any;
  label: string;
  type?: string;
  placeholder?: string;
  value?: string;
  br?: boolean;
  hide?: boolean;
  button?: any;
  onButtonClick?: (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>
  ) => void | undefined;
  onChange?: ((event: React.ChangeEvent<HTMLInputElement>) => void) | undefined;
  onBlur?: ((event: React.FocusEvent<HTMLInputElement>) => void) | undefined;
  full?: boolean;
  onFocus?: ((event: React.FocusEvent<HTMLInputElement>) => void) | undefined;
  dropdown?: any;
  required?: boolean;
  step?: number | string | undefined;
  name?: string;
}

const TextInput: React.FC<Props> = ({
  ref,
  label,
  type,
  placeholder,
  value,
  onChange,
  onBlur,
  button,
  onButtonClick,
  hide,
  br,
  full,
  onFocus,
  dropdown,
  required,
  step,
  name,
}) => {
  return (
    <>
      <div data-testid="textInputMainDiv" className={button ? "text-div" : ""}>
        <span data-testid="textInputLabel" className="text-label">
          {label}
        </span>
        {required && <span style={{ color: "red" }}>*</span>}
        <div className="text-combo">
          <input
            ref={ref}
            className={
              hide
                ? "text-input text-hide"
                : full
                ? "text-input text-input-full"
                : "text-input"
            }
            type={type ? type : "text"}
            placeholder={placeholder}
            onChange={onChange}
            value={value}
            onBlur={onBlur}
            onFocus={onFocus}
            data-testid="textInput"
            step={type === "number" ? step : undefined}
            name={name}
          />
          {button && (
            <button
              data-testid="textInputButton"
              className="text-button icon"
              onClick={onButtonClick}
            >
              {button}
            </button>
          )}
        </div>
      </div>
      {dropdown}
      {br && <br data-testid="textInputBr" />}
    </>
  );
};

export default TextInput;
