import React, { useEffect } from "react";
import { connect } from "react-redux";
import { isEmpty } from "lodash";

import "./styles.css";
import ValidatorSelect from "./ValidatorSelect";
import { getValidators, setRootValidator } from "../../core/actions";
import {
  getRootValidatorState,
  getValidatorsState,
} from "../../core/selectors";
import { RootValidator } from "../../core/interfaces/RootValidator";

interface Props {
  title: string;
  getValidators: Function;
  validators: any;
  setRootValidator: Function;
  rootValidator: RootValidator;
  showValidatorsList: boolean;
  component?: React.Component;
}

const CustomToolBar: React.FC<Props> = ({
  title,
  getValidators,
  validators,
  setRootValidator,
  rootValidator,
  showValidatorsList,
  component,
}) => {
  useEffect(() => {
    if (isEmpty(validators)) {
      getValidators();
    }
  }, []);

  useEffect(() => {
    if (isEmpty(rootValidator)) {
      setRootValidator(validators[0]);
    }
  }, [validators]);

  return (
    <>
      <div className="toolbar-details-row">
        <div className="toolbar-title-div">
          <span data-testid="toolbarTitle" className="custom-header-title">
            {title}
          </span>
          <span className="toolbar-sub-title">
            Connection is established and secure.
          </span>
        </div>
        {showValidatorsList && validators.length > 0 && (
          <ValidatorSelect
            selectedValidator={rootValidator}
            data={validators}
            onChange={(selectedValidator) => {
              setRootValidator(selectedValidator);
            }}
          />
        )}
        {component && component}
      </div>
      <hr />
    </>
  );
};

const mapStateToProps = (state) => ({
  validators: getValidatorsState(state),
  rootValidator: getRootValidatorState(state),
});

const mapDispatchToProps = {
  getValidators,
  setRootValidator,
};

export default connect(mapStateToProps, mapDispatchToProps)(CustomToolBar);
