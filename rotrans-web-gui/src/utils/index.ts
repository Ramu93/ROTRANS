export function formatNumber(x) {
  return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function isValidHex(str) {
  return str.match(/^([0-9a-f]{64})+$/i) !== null;
}

export function timestampToUTC(timestamp) {
  const a = new Date(timestamp * 1000);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const year = a.getFullYear();
  const month = months[a.getMonth()];
  const date = a.getDate();
  const hour = a.getHours();
  const min = a.getMinutes();
  const sec = a.getSeconds();
  return date + " " + month + " " + year + " " + hour + ":" + min + ":" + sec;
}

export const determineRoundStatus = (roundStatus) => {
  const STATUS_MESSAGES = ["AGREE_VALIDATOR", "AGREE_HASH", "AGREE_CONTENT"];

  return roundStatus === 0 ? "Unknown" : STATUS_MESSAGES[roundStatus - 1];
};

export const BASE_URL = process.env.REACT_APP_BASE_URL;
