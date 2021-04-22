import React, { useState, useEffect } from "react";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { toast } from "react-toastify";
import { connect } from "react-redux";
import { get, isEmpty } from "lodash";
import { useParams } from "react-router-dom";

import "./styles.css";
import BalanceIndicator from "../../../../components/BalanceIndicator";
import TextInput from "../../../../components/TextInput";
import ToolBar from "../../../../components/Toolbar/index";
import Dropdown from "../Dropdown";
import { getKeys, getBalance, getAgent, generateKeyPair } from "../../actions";
import { getBalanceState, getKeysState } from "../../selectors";
import { RootValidator } from "../../../../core/interfaces/RootValidator";
import Button from "../../../../components/Button";
import { KeyInterface } from "../../interfaces/KeyInterface";

interface InfoSegmentProps {
  keys: KeyInterface[];
  getBalance: Function;
  getAgent: Function;
  generateKeyPair: Function;
  balance: string;
  rootValidator: RootValidator;
}

const InfoSegment: React.FC<InfoSegmentProps> = ({
  keys,
  getBalance,
  getAgent,
  generateKeyPair,
  balance,
}) => {
  const { port } = useParams();
  const [hideSecretKey, setHideSecretKey] = useState(true);
  const [isDropdownOpen, setIsDropDownOpen] = useState(false);
  const [publicKey, setPublicKey] = useState(
    get(keys, `${keys.length - 1}.public_key`, "")
  );
  const [secretKey, setSecretKey] = useState(
    get(keys, `${keys.length - 1}.secret_key`, "")
  );
  const [isFirstLoad, setIsFirstLoad] = useState(true);

  useEffect(() => {
    if (isFirstLoad && isEmpty(keys)) {
      fetchData();
      setIsFirstLoad(false);
    } else if (!isFirstLoad) {
      // if it is not a first load and there no keys then generate a key pair
      generateKeyPair({ port });
    }
  }, []);

  const fetchData = () => {
    console.log("*******************", "fetch data again");
    getAgent({ port });
  };

  const handleGenerateKeysClick = () => generateKeyPair({ port });

  return (
    <>
      <div className="card">
        <ToolBar
          title="Transactions"
          component={
            <div className="generate-keys-btn">
              <Button label="Generate Keys" onClick={handleGenerateKeysClick} />
            </div>
          }
        />
        <div className="info-input-row">
          <>
            <div className="info-left-div">
              <>
                <TextInput
                  label="Public Key"
                  button={
                    <CopyToClipboard
                      text={publicKey}
                      onCopy={() =>
                        toast.dark("Public key copied!", {
                          toastId: 1,
                          position: "bottom-center",
                          autoClose: 2000,
                          hideProgressBar: true,
                          closeOnClick: true,
                          pauseOnHover: false,
                          draggable: false,
                          progress: 0,
                        })
                      }
                    >
                      <img src={require("../../../../assets/svg/copy.svg")} />
                    </CopyToClipboard>
                  }
                  value={publicKey}
                  onFocus={() => setIsDropDownOpen(true)}
                  // onBlur={() => setIsDropDownOpen(false)}
                  dropdown={
                    <Dropdown
                      isOpen={isDropdownOpen}
                      options={keys}
                      onSelection={(selectedOption) => {
                        setPublicKey(keys[selectedOption].public_key);
                        setSecretKey(keys[selectedOption].secret_key);
                        setIsDropDownOpen(false);
                      }}
                    />
                  }
                />
              </>
              <TextInput
                label="Secret Key"
                button={
                  <img src={require("../../../../assets/svg/lock.svg")} />
                }
                value={secretKey}
                onButtonClick={() => setHideSecretKey(!hideSecretKey)}
                hide={hideSecretKey}
              />
            </div>
            <div className="info-right-div" onClick={fetchData}>
              <BalanceIndicator balance={balance} />
            </div>
          </>
        </div>
      </div>
    </>
  );
};

const mapStateToProps = (state) => ({
  balance: getBalanceState(state),
  keys: getKeysState(state),
});

const mapDispatchToProps = {
  getKeys,
  getBalance,
  getAgent,
  generateKeyPair,
};

export default connect(mapStateToProps, mapDispatchToProps)(InfoSegment);
