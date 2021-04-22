import React, { useState, useEffect } from 'react';
import { isEmpty } from 'lodash';

import { RootValidator } from '../../core/interfaces/RootValidator';
import ValidatorSelectItem, {
  ValidatorSelectItemProps,
} from './ValidatorSelectorItem';

interface ValidatorSelectProps {
  data: ValidatorSelectItemProps[];
  onChange: Function;
  selectedValidator: RootValidator;
}

const ValidatorSelect: React.FC<ValidatorSelectProps> = ({
  data,
  onChange,
  selectedValidator,
}) => {
  const [selectedData, setSelectedData] = React.useState(
    isEmpty(selectedValidator) ? data[0] : selectedValidator
  );
  const [showPopup, setShowPopup] = React.useState(false);

  useEffect(() => {
    if (showPopup) {
      setShowPopup(false);
    }
  }, [selectedData]);

  const toggleShowPopup = () => setShowPopup(!showPopup);

  return (
    <div className="toolbar-profile-div">
      <ValidatorSelectItem
        agentName={selectedData.agentName}
        agentIp={selectedData.agentIp}
        isSelected
        onClick={toggleShowPopup}
      />
      {showPopup && (
        <div className="toolbar-profile-div-popup">
          {data.map((element, index) => (
            <ValidatorSelectItem
              agentName={element.agentName}
              agentIp={element.agentIp}
              onClick={() => {
                setSelectedData(data[index]);
                onChange(data[index]);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ValidatorSelect;
