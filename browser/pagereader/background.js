// Goop page reader. Does nothing until Goop asks for the page you are on; then it sends back the text of that one tab and forgets it.
// Goop (a program on this computer) reaches this extension through a native-messaging host (daemon/pagereader_host.py). Nothing here talks to the internet.
const HOST = "io.github.magonox.goop.pagereader";
let port = null;

function connect() {
  try { port = chrome.runtime.connectNative(HOST); } catch (e) { port = null; return; }
  port.onMessage.addListener(onRequest);
  port.onDisconnect.addListener(() => { port = null; setTimeout(connect, 5000); });     // the host is not installed yet, or the browser is closing
}

async function onRequest(msg) {
  let reply;
  try {
    reply = msg.cmd === "ping" ? { ok: true, version: 1 } : msg.cmd === "read" ? await readPage(msg) : { ok: false, error: "unknown command" };
  } catch (e) {
    reply = { ok: false, error: String((e && e.message) || e) };
  }
  if (port) port.postMessage({ id: msg.id, ...reply });
}

// The window title Goop knows is "<tab title> - Chromium": find the active tab that matches, else the active tab of the focused window.
async function pickTab(title) {
  const wanted = (title || "").replace(/ - (Chromium|Google Chrome|Brave|Microsoft Edge|Vivaldi)$/, "").trim();
  const active = await chrome.tabs.query({ active: true });
  if (wanted) {
    const exact = active.find(t => (t.title || "").trim() === wanted) || active.find(t => wanted && (t.title || "").trim().startsWith(wanted.slice(0, 40)));
    if (exact) return exact;
  }
  const win = await chrome.windows.getLastFocused({ populate: false }).catch(() => null);
  return active.find(t => win && t.windowId === win.id) || active[0] || null;
}

async function readPage(msg) {
  const tab = await pickTab(msg.title);
  if (!tab) return { ok: false, error: "no matching tab is open" };
  if (!/^(https?|file):/.test(tab.url || "")) return { ok: false, error: "this kind of page cannot be read (" + ((tab.url || "").split(":")[0] || "blank") + ")" };
  const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractPage, args: [Math.min(Math.max(+msg.max_chars || 12000, 500), 40000)] });
  return { ok: true, tab_title: tab.title || "", url: tab.url, ...(res && res.result) };
}

// Runs inside the page. The readable text, not the menus: the main article if there is one, else the paragraphs, headings and list items outside navigation, footers and sidebars.
function extractPage(max) {
  const skip = "nav,footer,aside,header,form,[role=navigation],[role=banner],[role=contentinfo],[aria-hidden=true],script,style,noscript";
  const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const mains = [...document.querySelectorAll("article, main, [role=main], #content, #main, .content")].sort((a, b) => (b.innerText || "").length - (a.innerText || "").length);
  const root = mains[0] && (mains[0].innerText || "").length > 500 ? mains[0] : document.body;
  const blocks = [...root.querySelectorAll("h1,h2,h3,h4,p,li,pre,blockquote,td,th,figcaption,dt,dd")]
    .filter(el => !el.closest(skip) && visible(el))
    .map(el => (el.innerText || "").replace(/\s+/g, " ").trim())
    .filter((t, i, all) => t.length > 1 && t !== all[i - 1]);
  let text = blocks.join("\n");
  if (text.length < 200) text = (root.innerText || "").replace(/\n{3,}/g, "\n\n").trim();         // pages without paragraph tags
  const meta = document.querySelector('meta[name="description"],meta[property="og:description"]');
  const headings = [...document.querySelectorAll("h1,h2,h3")].filter(h => !h.closest(skip) && visible(h)).map(h => (h.innerText || "").trim()).filter(Boolean).slice(0, 30);
  return {
    title: document.title, text: text.slice(0, max), truncated: text.length > max, chars: text.length,
    selection: String(getSelection() || "").slice(0, 2000), headings, description: meta ? meta.content : "", lang: document.documentElement.lang || "",
  };
}

connect();
