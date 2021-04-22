import React, { useState } from "react";
import { connect } from "react-redux";
import { Helmet } from "react-helmet";
import { useParams } from "react-router-dom";

import Loader from "../../components/Loader";
import InfoSegment from "./components/InfoSegment/index";
import TransactionCard from "./components/TransactionsCard";
import { getLoadingState } from "./selectors";
import FloatingButton from "../../components/FloatingButton/index";
import Modal from "../../components/Modal";
import TextInput from "../../components/TextInput";
import { addKey } from "./actions";
import MenuBar from "../../components/MenuBar";

const Transactions = ({ isLoading, addKey }) => {
  const [showModal, setShowModal] = useState(false);
  const [key, setKey] = useState("");
  const { port } = useParams();

  const handleAddKey = () => {
    if (key !== "") {
      addKey({ key, port });
      setKey("");
    }
  };

  return (
    <>
      <Helmet>
        <title>{port + " ROTRANS - Transactions"}</title>
      </Helmet>
      <div className="container">
        <MenuBar port={port} />
        <div className="workspace">
          {isLoading ? (
            <Loader visible />
          ) : (
            <>
              <InfoSegment />
              <TransactionCard />
              <FloatingButton
                icon={<i className="fa fa-plus float-content"></i>}
                handleClick={() => setShowModal(true)}
              />
              <Modal
                show={showModal}
                handleClose={() => setShowModal(false)}
                confirmLabel="Add"
                handleConfirm={handleAddKey}
              >
                <TextInput
                  label="Pre-generated Secret Key"
                  placeholder="Enter the value..."
                  type="text"
                  value={key}
                  onChange={(event) => setKey(event.target.value)}
                  full
                />
              </Modal>
            </>
          )}
        </div>
      </div>
    </>
  );
};

const mapStateToProps = (state) => ({
  isLoading: getLoadingState(state),
});

const mapDispatchToProps = {
  addKey,
};

export default connect(mapStateToProps, mapDispatchToProps)(Transactions);
