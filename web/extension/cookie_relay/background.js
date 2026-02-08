const DEFAULT_API = "http://127.0.0.1:5010/api/chat/cookies/save";

function setBadge(text, color) {
  chrome.action.setBadgeText({ text: text || "" });
  if (color) {
    chrome.action.setBadgeBackgroundColor({ color });
  }
}

async function saveCookiesForActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs && tabs[0];
  if (!tab || !tab.url) {
    setBadge("ERR", "#d32f2f");
    return;
  }
  const url = new URL(tab.url);
  const hostname = url.hostname;
  if (!hostname) {
    setBadge("ERR", "#d32f2f");
    return;
  }
  let cookies = await chrome.cookies.getAll({ url: tab.url });
  if (!cookies || cookies.length === 0) {
    cookies = await chrome.cookies.getAll({ domain: hostname });
  }
  if ((!cookies || cookies.length === 0) && hostname.includes(".")) {
    const parts = hostname.split(".");
    if (parts.length > 2) {
      const parent = parts.slice(-2).join(".");
      cookies = await chrome.cookies.getAll({ domain: parent });
    }
  }
  const payload = { domain: hostname, cookies };
  const res = await fetch(DEFAULT_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "save failed");
  }
  setBadge("OK", "#2e7d32");
  setTimeout(() => setBadge(""), 1500);
}

chrome.action.onClicked.addListener(() => {
  saveCookiesForActiveTab().catch((err) => {
    console.error(err);
    setBadge("ERR", "#d32f2f");
    setTimeout(() => setBadge(""), 1500);
  });
});
