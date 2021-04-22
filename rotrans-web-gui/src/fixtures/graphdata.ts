import { key } from "./constants";

export default {
  nodes: [
    {
      id: "a1",
      color: "#6435C9",
      meta: {
        isTransaction: false,
        prev_ack: "genesis1234",
        txn_id: "txn1234",
        validator: "validator1234",
      },
    },
    {
      id: "a2",
      color: "#6435C9",
      meta: { isTransaction: false, stake: "3000", balance: "390" },
    },
    {
      id: "a3",
      color: "#6435C9",
      meta: { isTransaction: false, stake: "2300", balance: "860" },
    },
    {
      id: "a4",
      color: "#6435C9",
      meta: { isTransaction: false, stake: "3065", balance: "150" },
    },
    {
      id: "123",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "2",
        isConfirmed: true,
        total_inputs: "10",
        total_outputs: "9.8",
        total_fees: "0.2",
      },
    },
    {
      id: "124",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "10",
        isConfirmed: true,
      },
    },
    {
      id: "125",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "20",
        isConfirmed: true,
      },
    },
    {
      id: "126",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "25",
        isConfirmed: true,
      },
    },
    {
      id: "127",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "40",
        isConfirmed: true,
      },
    },
    {
      id: "128",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "20",
        isConfirmed: true,
      },
    },
    {
      id: "129",
      symbolType: "square",
      color: "#39B814",
      meta: { isTransaction: true, origin: key, value: "3", isConfirmed: true },
    },
    {
      id: "130",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "18",
        isConfirmed: true,
      },
    },
    {
      id: "131",
      symbolType: "square",
      color: "#39B814",
      meta: { isTransaction: true, origin: key, value: "9", isConfirmed: true },
    },
    {
      id: "132",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "31",
        isConfirmed: true,
      },
    },
    {
      id: "133",
      symbolType: "square",
      color: "#39B814",
      meta: { isTransaction: true, origin: key, value: "3", isConfirmed: true },
    },
    {
      id: "134",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "18",
        isConfirmed: true,
      },
    },
    {
      id: "135",
      symbolType: "square",
      color: "#39B814",
      meta: {
        isTransaction: true,
        origin: key,
        value: "31",
        isConfirmed: true,
      },
    },
  ],
  links: [
    { source: "a1", target: "123" },
    { source: "a2", target: "123" },
    { source: "a2", target: "124" },
    { source: "a3", target: "124" },
    { source: "a3", target: "123" },
    { source: "a3", target: "125" },
    { source: "a4", target: "126" },
    { source: "a4", target: "127" },
    { source: "a4", target: "128" },
    { source: "a3", target: "126" },
    { source: "a3", target: "127" },
    { source: "a3", target: "128" },
    { source: "a1", target: "126" },
    { source: "a1", target: "127" },
    { source: "a1", target: "128" },

    { source: "a3", target: "129" },
    { source: "a3", target: "130" },
    { source: "a3", target: "131" },
    { source: "a3", target: "132" },
    { source: "a3", target: "133" },
    { source: "a3", target: "134" },
    { source: "a3", target: "135" },

    { source: "a2", target: "129" },
    { source: "a2", target: "130" },
    { source: "a2", target: "133" },
    { source: "a2", target: "135" },

    { source: "a4", target: "131" },
    { source: "a4", target: "132" },
    { source: "a4", target: "134" },
    { source: "a4", target: "135" },

    { source: "124", target: "123", color: "#000000" },
    { source: "125", target: "124", color: "#000000" },
    { source: "126", target: "125", color: "#000000" },
    { source: "127", target: "126", color: "#000000" },
    { source: "128", target: "126", color: "#000000" },
    { source: "128", target: "127", color: "#000000" },
    { source: "129", target: "128", color: "#000000" },
    { source: "131", target: "129", color: "#000000" },

    { source: "130", target: "129", color: "#000000" },
    { source: "131", target: "130", color: "#000000" },
    { source: "132", target: "131", color: "#000000" },
  ],
};
