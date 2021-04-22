import React from "react";
import Radio from "@material-ui/core/Radio";
import RadioGroup from "@material-ui/core/RadioGroup";
import FormControlLabel from "@material-ui/core/FormControlLabel";
import FormControl from "@material-ui/core/FormControl";
import FormLabel from "@material-ui/core/FormLabel";

import "./styles.css";

interface Props {
  onChange: Function;
}

const RadioButton: React.FC<Props> = ({ onChange }) => {
  const [value, setValue] = React.useState("recipient");

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setValue((event.target as HTMLInputElement).value);
  };

  React.useEffect(() => onChange(value), [value]);

  return (
    <div className="radio-component">
      <FormControl component="fieldset">
        <FormLabel component="legend" className="radio-label">
          Mode of Transfer
        </FormLabel>
        <RadioGroup
          className="radio-group"
          aria-label="transferMode"
          name="transferMode"
          value={value}
          onChange={handleChange}
        >
          <FormControlLabel
            value="recipient"
            control={<Radio />}
            label="Recipient"
          />
          <FormControlLabel
            value="delegate"
            control={<Radio />}
            label="Delegate"
          />
        </RadioGroup>
      </FormControl>
    </div>
  );
};

export default RadioButton;
