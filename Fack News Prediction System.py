from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree


HOST = "127.0.0.1"
PORT = 8000
MAX_CLAIM_LENGTH = 4000
FACTCHECK_SEARCH_URL = "https://www.factcheck.org/wp-json/wp/v2/posts"
GOOGLE_NEWS_SEARCH_URL = "https://news.google.com/rss/search"
TRUSTED_RESEARCH_SITES = (
    "factcheck.org", "apnews.com", "reuters.com", "fullfact.org",
    "snopes.com", "who.int", "cdc.gov",
)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#075e54">
  <title>Fake News Checker — pause before you forward</title>
  <style>
    :root { color-scheme: light; --green:#075e54; --ink:#172b25; --muted:#64736d; --paper:#f5f7f4; --line:#e4eae5; font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; background:var(--paper); color:var(--ink); }
    button,textarea { font:inherit; } button { cursor:pointer; }
    .topbar { height:66px; display:flex; align-items:center; justify-content:space-between; padding:0 max(22px,calc((100vw - 1100px)/2)); background:#fff; border-bottom:1px solid var(--line); }
    .brand { display:flex; align-items:center; gap:10px; font-weight:750; letter-spacing:-.03em; }
    .brand-mark { width:34px; height:34px; display:grid; place-items:center; border-radius:11px; color:#fff; background:var(--green); font-size:17px; }
    .top-note { color:var(--muted); font-size:13px; }
    main { width:min(1060px,calc(100% - 36px)); margin:48px auto 64px; }
    .intro { max-width:700px; margin-bottom:30px; }
    .eyebrow { color:var(--green); font-size:12px; font-weight:750; letter-spacing:.13em; text-transform:uppercase; }
    h1 { margin:10px 0 9px; font-size:clamp(30px,5vw,46px); letter-spacing:-.055em; line-height:1.08; }
    .intro p { margin:0; max-width:610px; color:var(--muted); line-height:1.65; }
    .layout { display:grid; grid-template-columns:minmax(0,1.12fr) minmax(300px,.88fr); gap:22px; }
    .card { background:#fff; border:1px solid var(--line); border-radius:20px; overflow:hidden; }
    .section-head { display:flex; align-items:center; justify-content:space-between; padding:18px 20px; border-bottom:1px solid var(--line); }
    .section-head h2 { margin:0; font-size:15px; letter-spacing:-.015em; }
    .demo-label { color:var(--muted); font-size:11px; font-weight:650; }
    .chat-head { display:flex; align-items:center; gap:11px; padding:15px 18px; color:#fff; background:var(--green); }
    .avatar { width:37px; height:37px; border-radius:50%; display:grid; place-items:center; background:#d5eee4; color:var(--green); font-weight:750; }
    .chat-name { font-size:14px; font-weight:700; } .chat-status { margin-top:2px; color:#d4e6df; font-size:11px; }
    .chat { min-height:245px; padding:18px; color:#172b25; background-color:#efeae2; background-image:radial-gradient(#e6dfd4 .7px,transparent .7px); background-size:13px 13px; }
    .date-chip { width:max-content; margin:0 auto 17px; padding:6px 10px; border-radius:8px; background:#fff; color:var(--muted); font-size:10px; }
    .bubble { max-width:94%; width:max-content; padding:11px 13px 9px; border-radius:4px 14px 14px 14px; background:#fff; box-shadow:0 1px 2px #163c2612; }
    .sender { margin-bottom:6px; color:#00a884; font-size:11px; font-weight:700; }
    .forwarded-label { display:flex; align-items:center; gap:4px; margin-bottom:5px; color:#667781; font-size:11px; font-style:italic; }
    .forwarded-arrow { font-size:15px; font-style:normal; line-height:1; }
    .message-text { white-space:pre-wrap; color:#172b25; font-size:13px; line-height:1.55; user-select:text; }
    .time { margin-top:6px; color:#667781; font-size:10px; text-align:right; }
    .select-hint { margin:13px 0 0; color:#52645b; font-size:11px; line-height:1.5; }
    .compose { padding:18px 20px 20px; border-top:1px solid var(--line); }
    .compose label { display:block; margin-bottom:8px; font-size:12px; font-weight:700; }
    textarea { display:block; width:100%; min-height:86px; resize:vertical; padding:12px; border:1px solid #dce4de; border-radius:11px; color:var(--ink); outline:none; font-size:12px; line-height:1.55; }
    textarea:focus { border-color:#58a58e; box-shadow:0 0 0 3px #0c806d14; }
    .paste-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:10px; }
    .small-note { color:var(--muted); font-size:10px; line-height:1.45; }
    .button { border:0; border-radius:10px; padding:10px 14px; color:#fff; background:var(--green); font-size:12px; font-weight:700; transition:transform .15s,background .15s; }
    .button:hover { background:#064a42; transform:translateY(-1px); } .button:disabled { opacity:.6; cursor:wait; }
    .button.secondary { color:var(--green); background:#e8f4ee; } .button.secondary:hover { background:#d9eee4; }
    .result-card { padding:20px; }
    .result-empty { min-height:320px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; }
    .empty-icon { width:54px; height:54px; display:grid; place-items:center; margin-bottom:13px; border-radius:18px; background:#eef5ef; font-size:24px; }
    .result-empty h3 { margin:0 0 7px; font-size:15px; }
    .result-empty p { max-width:230px; margin:0; color:var(--muted); font-size:12px; line-height:1.6; }
    .result { display:none; }
    .result-kicker { color:var(--green); font-size:10px; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
    .verdict { margin:9px 0 3px; font-size:28px; letter-spacing:-.04em; }
    .confidence { color:#97621b; font-size:11px; font-weight:700; }
    .claim-preview { margin:15px 0; padding:12px; border-left:3px solid #9ab6a9; border-radius:0 9px 9px 0; background:#f5f8f5; color:#42534b; font-size:11px; line-height:1.55; overflow-wrap:anywhere; }
    .signals-title { margin:17px 0 9px; font-size:12px; font-weight:750; }
    .signals { list-style:none; margin:0; padding:0; }
    .signals li { display:flex; gap:9px; margin:9px 0; color:#4a5d53; font-size:11px; line-height:1.5; }
    .signals li::before { content:"•"; color:#cf8b32; font-size:17px; line-height:12px; }
    .sources-title { margin:18px 0 8px; font-size:12px; font-weight:750; }
    .source-summary { margin:0 0 9px; color:#4a5d53; font-size:11px; line-height:1.55; }
    .sources { list-style:none; margin:0; padding:0; }
    .sources li { margin:8px 0; padding:10px; border:1px solid var(--line); border-radius:10px; font-size:11px; line-height:1.5; }
    .sources a { color:var(--green); font-weight:700; text-decoration:none; }
    .sources a:hover { text-decoration:underline; }
    .source-excerpt { display:block; margin-top:5px; color:#52645b; font-weight:400; }
    .source-byline { display:block; margin-top:5px; color:var(--muted); font-size:10px; }
    .followup { display:none; margin-top:18px; padding-top:15px; border-top:1px solid var(--line); }
    .followup h4 { margin:0 0 5px; font-size:13px; }
    .followup p { margin:0 0 10px; color:var(--muted); font-size:10px; line-height:1.5; }
    .followup-form { display:flex; gap:8px; }
    .followup-form input { flex:1; min-width:0; padding:10px; border:1px solid #dce4de; border-radius:10px; color:var(--ink); font:inherit; font-size:11px; }
    .followup-form input:focus { border-color:#58a58e; outline:2px solid #0c806d14; }
    .followup-answer { margin-top:10px; color:#42534b; font-size:11px; line-height:1.55; }
    .honesty { margin-top:15px; padding:11px; border-radius:10px; background:#fff8e9; color:#6b562b; font-size:10px; line-height:1.55; }
    .search-link { display:block; margin-top:14px; text-align:center; text-decoration:none; }
    .method { margin-top:10px; color:var(--muted); font-size:11px; line-height:1.6; }
    .method summary { cursor:pointer; color:var(--green); font-weight:700; }
    .method a { color:var(--green); }
    .footer { margin-top:21px; color:var(--muted); font-size:10px; line-height:1.6; text-align:center; }
    .selection-action { position:fixed; z-index:5; display:none; padding:9px 12px; border:0; border-radius:10px; background:#153d34; color:#fff; box-shadow:0 6px 22px #0b251d35; font-size:12px; font-weight:700; }
    .selection-action:hover { background:var(--green); }
    .overlay { position:fixed; z-index:10; inset:0; display:none; place-items:center; padding:20px; background:#10241db3; backdrop-filter:blur(3px); }
    .dialog { width:min(430px,100%); padding:24px; border-radius:19px; background:#fff; box-shadow:0 22px 70px #0003; }
    .dialog-mark { width:40px; height:40px; display:grid; place-items:center; margin-bottom:14px; border-radius:13px; background:#e8f4ee; font-size:19px; }
    .dialog h2 { margin:0; font-size:20px; letter-spacing:-.03em; }
    .dialog p { margin:8px 0 15px; color:var(--muted); font-size:12px; line-height:1.6; }
    .dialog-claim { max-height:130px; overflow:auto; padding:11px; border-radius:10px; background:#f5f7f4; color:#46594f; font-size:11px; line-height:1.55; white-space:pre-wrap; overflow-wrap:anywhere; }
    .dialog-actions { display:flex; justify-content:flex-end; gap:9px; margin-top:18px; }
    .toast { position:fixed; z-index:12; left:50%; bottom:22px; display:none; transform:translateX(-50%); padding:11px 15px; border-radius:10px; color:#fff; background:#263c33; font-size:12px; }
    @media(max-width:760px) { main { margin-top:30px; } .layout { grid-template-columns:1fr; } .result-empty { min-height:210px; } .top-note { display:none; } }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><span class="brand-mark">✓</span><span>Fake News Checker</span></div>
    <div class="top-note">Pause, check the sources, then decide</div>
  </header>
  <main>
    <section class="intro">
      <div class="eyebrow">Pause before you share</div>
      <h1>Curious about a message?<br>Check it, not the person.</h1>
      <p>Paste a forwarded message or enter any news topic. We’ll find related coverage and help you explore what to check next.</p>
    </section>
    <div class="layout">
      <section class="card" aria-label="WhatsApp message demo">
        <div class="section-head"><h2>Try it with a forwarded message</h2><span class="demo-label">INTERACTIVE DEMO</span></div>
        <div class="chat-head"><div class="avatar">F</div><div><div class="chat-name">Family group</div><div class="chat-status">online</div></div></div>
        <div class="chat">
          <div class="date-chip">TODAY</div>
          <div class="bubble">
            <div class="sender">Auntie</div>
            <div class="forwarded-label"><span class="forwarded-arrow" aria-hidden="true">↪</span><span>Forwarded</span></div>
            <div class="message-text" id="sampleMessage">The city council has approved a new city-wide curfew starting tomorrow. Share this before it gets deleted!</div>
            <div class="time">10:42 AM</div>
          </div>
          <p class="select-hint">Highlight any part of the message above. On a phone, press and hold the text. Then choose <b>Check this message</b>.</p>
        </div>
        <div class="compose">
          <label for="pasteText">Search a news claim or paste a WhatsApp message</label>
          <textarea id="pasteText" maxlength="4000" placeholder="Enter a news topic or paste a forwarded message…"></textarea>
          <div class="paste-row">
            <span class="small-note">Search text goes to Google News and FactCheck.org.<br>This demo doesn’t store your message.</span>
            <button class="button" id="pasteCheck" type="button">Search this news</button>
          </div>
        </div>
      </section>
      <section class="card" aria-live="polite" aria-label="Message check result">
        <div class="section-head"><h2>Message check</h2><span class="demo-label">EXPLAINABLE</span></div>
        <div class="result-card">
          <div class="result-empty" id="emptyState">
            <div class="empty-icon">⌕</div><h3>Your check will appear here</h3>
            <p>Choose a message first. We’ll show language signals, not an unsupported true-or-fake verdict.</p>
          </div>
          <div class="result" id="result">
            <div class="result-kicker">A careful first look</div>
            <h3 class="verdict">Needs verification</h3>
            <div class="confidence">No conclusion until the evidence is checked</div>
            <div class="claim-preview" id="claimPreview"></div>
            <div class="signals-title">What we noticed</div><ul class="signals" id="signals"></ul>
            <div class="sources-title">Related news and fact-checks</div>
            <p class="source-summary" id="sourceSummary" role="status"></p>
            <ul class="sources" id="sources"></ul>
            <div class="honesty">Wording clues and missing search results are not proof. Read the linked source, check the date and context, and compare independent reporting before deciding whether to share.</div>
            <a class="button search-link" id="searchLink" href="#" target="_blank" rel="noopener noreferrer">Search more research ↗</a>
            <details class="method">
              <summary>How does this check work?</summary>
              <p>We look for common wording patterns, then search Google News and FactCheck.org for related coverage. Headlines and related articles are context, not an automatic verdict. If there is no match or a source is unavailable, we say so rather than guessing.</p>
              <p>For more perspectives, search trusted sources such as <a href="https://apnews.com/" target="_blank" rel="noopener noreferrer">AP News</a>, <a href="https://www.reuters.com/" target="_blank" rel="noopener noreferrer">Reuters</a>, <a href="https://fullfact.org/" target="_blank" rel="noopener noreferrer">Full Fact</a>, <a href="https://www.snopes.com/" target="_blank" rel="noopener noreferrer">Snopes</a>, <a href="https://www.who.int/" target="_blank" rel="noopener noreferrer">WHO</a>, and <a href="https://www.cdc.gov/" target="_blank" rel="noopener noreferrer">CDC</a>.</p>
            </details>
            <section class="followup" id="followup" aria-label="Ask a follow-up question">
              <h4>Ask a follow-up question</h4>
              <p>Ask for more context or search a related angle. Answers are based on the headlines linked above; open the articles to check the full evidence.</p>
              <form class="followup-form" id="followupForm">
                <input id="followupQuestion" maxlength="500" placeholder="What else should I look into?" aria-label="Follow-up question">
                <button class="button" id="followupSubmit" type="submit">Ask</button>
              </form>
              <div class="followup-answer" id="followupAnswer" aria-live="polite"></div>
            </section>
          </div>
        </div>
      </section>
    </div>
    <div class="footer">A starting point, not a verdict · Check the full source and date before sharing · Your message is not stored by this demo.</div>
  </main>
  <button class="selection-action" id="selectionAction" type="button">⌕ &nbsp;Check this message</button>
  <div class="overlay" id="confirmOverlay" role="dialog" aria-modal="true" aria-labelledby="dialogTitle">
    <div class="dialog">
      <div class="dialog-mark">⌕</div><h2 id="dialogTitle">Check this message?</h2>
      <p>We’ll look for common wording clues and search for related news from multiple outlets. We won’t label a claim true or false without evidence.</p>
      <div class="dialog-claim" id="dialogClaim"></div>
      <div class="dialog-actions">
        <button class="button secondary" id="cancelCheck" type="button">Not now</button>
        <button class="button" id="confirmCheck" type="button">Check message</button>
      </div>
    </div>
  </div>
  <div class="toast" id="toast" role="status"></div>
  <script>
    (() => {
      const action = document.getElementById("selectionAction");
      const overlay = document.getElementById("confirmOverlay");
      const dialogClaim = document.getElementById("dialogClaim");
      const toast = document.getElementById("toast");
      let selectedClaim = "";
      let toastTimer;
      function showToast(message) {
        toast.textContent = message;
        toast.style.display = "block";
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { toast.style.display = "none"; }, 3200);
      }
      function hideAction() { action.style.display = "none"; }
      function inspectSelection(event) {
        const selection = window.getSelection();
        const text = selection ? selection.toString().trim() : "";
        const anchor = selection ? selection.anchorNode : null;
        const message = document.getElementById("sampleMessage");
        if (event && event.target && !message.contains(event.target)) { hideAction(); return; }
        if (!text || !anchor || !message.contains(anchor)) { hideAction(); return; }
        selectedClaim = text.slice(0, 4000);
        const rect = selection.getRangeAt(0).getBoundingClientRect();
        const x = event && Number.isFinite(event.clientX) && event.clientX > 0 ? event.clientX : rect.left;
        const y = event && Number.isFinite(event.clientY) && event.clientY > 0 ? event.clientY : rect.bottom;
        action.style.left = `${Math.max(8, Math.min(x, window.innerWidth - 180))}px`;
        action.style.top = `${Math.max(8, Math.min(y + 8, window.innerHeight - 50))}px`;
        action.style.display = "block";
      }
      function openConfirmation(claim) {
        if (!claim.trim()) { showToast("Select or paste a message first."); return; }
        selectedClaim = claim.trim().slice(0, 4000);
        dialogClaim.textContent = selectedClaim;
        overlay.style.display = "grid";
        hideAction();
        document.getElementById("confirmCheck").focus();
      }
      async function analyzeClaim() {
        const button = document.getElementById("confirmCheck");
        button.disabled = true;
        button.textContent = "Searching…";
        try {
          const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: selectedClaim })
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Could not check this message.");
          document.getElementById("emptyState").style.display = "none";
          document.getElementById("result").style.display = "block";
          document.getElementById("claimPreview").textContent = result.claim;
          const list = document.getElementById("signals");
          list.replaceChildren();
          result.signals.forEach((signal) => {
            const item = document.createElement("li");
            item.textContent = signal;
            list.appendChild(item);
          });
          document.getElementById("sourceSummary").textContent = result.source_summary;
          const sources = document.getElementById("sources");
          sources.replaceChildren();
          result.sources.forEach((source) => {
            const item = document.createElement("li");
            const link = document.createElement("a");
            link.href = source.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = source.title;
            item.appendChild(link);
            const excerpt = document.createElement("span");
            excerpt.className = "source-excerpt";
            excerpt.textContent = source.excerpt;
            item.appendChild(excerpt);
            const byline = document.createElement("span");
            byline.className = "source-byline";
            byline.textContent = [source.publisher, source.published].filter(Boolean).join(" · ");
            item.appendChild(byline);
            sources.appendChild(item);
          });
          document.getElementById("searchLink").href = result.search_url;
          document.getElementById("followup").style.display = "block";
          document.getElementById("followupAnswer").textContent = "";
          overlay.style.display = "none";
          document.getElementById("pasteText").value = "";
          document.querySelector(".card[aria-label='Message check result']").scrollIntoView({ behavior:"smooth", block:"nearest" });
        } catch (error) {
          showToast(error.message);
        } finally {
          button.disabled = false;
          button.textContent = "Check message";
        }
      }
      async function askFollowup(event) {
        event.preventDefault();
        const input = document.getElementById("followupQuestion");
        const button = document.getElementById("followupSubmit");
        const answer = document.getElementById("followupAnswer");
        const question = input.value.trim();
        if (!question) { showToast("Type a question to search."); return; }
        button.disabled = true;
        answer.textContent = "Searching current coverage for your question…";
        try {
          const response = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ claim: document.getElementById("claimPreview").textContent, question })
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Could not search this question.");
          answer.replaceChildren();
          const explanation = document.createElement("p");
          explanation.textContent = result.answer;
          answer.appendChild(explanation);
          result.sources.forEach((source) => {
            const item = document.createElement("div");
            item.className = "sources";
            const link = document.createElement("a");
            link.href = source.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = source.title;
            item.appendChild(link);
            const byline = document.createElement("span");
            byline.className = "source-byline";
            byline.textContent = [source.publisher, source.published].filter(Boolean).join(" · ");
            item.appendChild(byline);
            answer.appendChild(item);
          });
          input.value = "";
        } catch (error) {
          answer.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      }
      document.addEventListener("mouseup", inspectSelection);
      document.addEventListener("touchend", (event) => setTimeout(() => inspectSelection(event), 0));
      document.addEventListener("selectionchange", () => { if (window.getSelection()?.isCollapsed) hideAction(); });
      action.addEventListener("mousedown", (event) => event.preventDefault());
      action.addEventListener("click", () => openConfirmation(selectedClaim));
      document.getElementById("cancelCheck").addEventListener("click", () => { overlay.style.display = "none"; });
      overlay.addEventListener("click", (event) => { if (event.target === overlay) overlay.style.display = "none"; });
      document.addEventListener("keydown", (event) => { if (event.key === "Escape") overlay.style.display = "none"; });
      document.getElementById("confirmCheck").addEventListener("click", analyzeClaim);
      document.getElementById("pasteCheck").addEventListener("click", () => openConfirmation(document.getElementById("pasteText").value));
      document.getElementById("followupForm").addEventListener("submit", askFollowup);
    })();
  </script>
</body>
</html>
"""


def _research_terms(claim: str) -> str:
    stop_words = {
        "about", "after", "again", "also", "because", "before", "being", "could",
        "what", "when", "where", "why", "how", "which", "who", "whom", "whose",
        "can", "did", "does", "tell", "show", "find", "say",
        "every", "from", "have", "into", "just", "more", "other", "over", "share",
        "should", "that", "their", "there", "these", "they", "this", "those",
        "through", "with", "would", "your", "forwarded", "received", "send",
        "share", "forward", "urgent", "everyone", "now", "today", "say", "says",
        "all", "every", "some", "many", "much", "fake", "news", "check", "checker",
        "fact", "facts", "claim", "claims", "true", "false", "real",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", claim.casefold())
    terms = [word for word in words if word not in stop_words]
    return " ".join(terms[:12])


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _search_factcheck_org(claim: str) -> tuple[list[dict[str, str]], str]:
    query = _research_terms(claim)
    query_terms = query.split()
    if len(query_terms) < 2:
        return [], "There are not enough specific words to look for related FactCheck.org articles."
    request_url = (
        f"{FACTCHECK_SEARCH_URL}?search={quote_plus(query)}&per_page=3"
        "&_fields=link,title,excerpt"
    )
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "FakeNewsChecker/1.0 (public fact-check archive lookup)",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        print(f"FactCheck.org search returned HTTP {error.code}.")
        return [], "FactCheck.org could not be reached just now. Try searching more research below."
    except (URLError, TimeoutError) as error:
        print(f"FactCheck.org search failed ({type(error).__name__}).")
        return [], "FactCheck.org could not be reached just now. Try searching more research below."
    except OSError as error:
        print(f"FactCheck.org search failed ({type(error).__name__}).")
        return [], "FactCheck.org could not be reached just now. Try searching more research below."
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"FactCheck.org returned an unreadable response: {error}")
        return [], "FactCheck.org returned an unreadable response. Try searching more research below."

    if not isinstance(payload, list):
        return [], "FactCheck.org returned an unexpected response. Try searching more research below."

    sources = []
    for result in payload:
        if not isinstance(result, dict):
            continue
        url = result.get("link")
        title_data = result.get("title")
        excerpt_data = result.get("excerpt")
        title = title_data.get("rendered") if isinstance(title_data, dict) else None
        excerpt = excerpt_data.get("rendered") if isinstance(excerpt_data, dict) else None
        if not isinstance(url, str) or not isinstance(title, str):
            continue
        if not re.match(r"^https://(?:www\.)?factcheck\.org/", url):
            continue
        searchable_text = _plain_text(f"{title} {excerpt or ''}").casefold()
        matching_terms = sum(
            bool(re.search(rf"\b{re.escape(term)}\w*\b", searchable_text))
            for term in query_terms
        )
        if matching_terms < min(2, len(query_terms)):
            continue
        sources.append(
            {
                "url": url,
                "title": _plain_text(title)[:200],
                "excerpt": _plain_text(excerpt or "")[:500],
            }
        )

    if sources:
        summary = (
            "Related articles found in FactCheck.org’s public archive. "
            "Read each article for its evidence and context; these results alone do not settle the claim."
        )
    else:
        summary = (
            "No matching articles found in FactCheck.org’s searchable archive for these words. "
            "That is not evidence that the claim is true or false."
        )
    return sources, summary


def _search_google_news(claim: str) -> tuple[list[dict[str, str]], str]:
    query = _research_terms(claim)
    if len(query.split()) < 2:
        return [], "Enter a little more detail to search for related news coverage."
    request_url = (
        f"{GOOGLE_NEWS_SEARCH_URL}?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN%3Aen"
    )
    request = Request(
        request_url,
        headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            feed = ElementTree.fromstring(response.read(1_000_001))
    except HTTPError as error:
        print(f"Google News search returned HTTP {error.code}.")
        return [], "Live news search is unavailable right now. Try the broader research link below."
    except (URLError, TimeoutError, OSError) as error:
        print(f"Google News search failed ({type(error).__name__}).")
        return [], "Live news search is unavailable right now. Try the broader research link below."
    except ElementTree.ParseError as error:
        print(f"Google News returned an unreadable feed: {error}")
        return [], "Live news search returned an unreadable response. Try the broader research link below."

    if feed.tag != "rss" or len(feed.findall("./channel/item")) == 0:
        return [], "No related recent headlines were found. That does not prove the claim true or false."

    sources: list[dict[str, str]] = []
    for item in feed.findall("./channel/item")[:5]:
        title = item.findtext("title", "").strip()
        article_url = item.findtext("link", "").strip()
        source_element = item.find("source")
        publisher = (source_element.text or "").strip() if source_element is not None else ""
        publisher_url = source_element.get("url", "") if source_element is not None else ""
        published_raw = item.findtext("pubDate", "").strip()
        if not title or not article_url.startswith("https://news.google.com/rss/articles/"):
            continue
        if publisher_url and not publisher_url.startswith("https://"):
            continue
        try:
            published = parsedate_to_datetime(published_raw).strftime("%b %d, %Y")
        except (TypeError, ValueError, OverflowError):
            published = ""
        sources.append(
            {
                "url": article_url,
                "title": _plain_text(title)[:200],
                "excerpt": "",
                "publisher": _plain_text(publisher)[:100],
                "published": published,
            }
        )

    summary = (
        "Related headlines from Google News. Headlines are leads, not fact-check verdicts; open the articles to review the reporting."
        if sources
        else "No related recent headlines were found. That does not prove the claim true or false."
    )
    return sources, summary


def _search_everywhere(claim: str) -> tuple[list[dict[str, str]], str]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        news_future = executor.submit(_search_google_news, claim)
        factcheck_future = executor.submit(_search_factcheck_org, claim)
        news_sources, news_summary = news_future.result()
        factcheck_sources, factcheck_summary = factcheck_future.result()

    combined = news_sources + factcheck_sources
    if news_sources and factcheck_sources:
        summary = f"{news_summary} {factcheck_summary}"
    elif news_sources:
        summary = news_summary
    elif factcheck_sources:
        summary = factcheck_summary
    elif "unavailable" in news_summary.casefold() or "could not be reached" in factcheck_summary.casefold():
        summary = (
            "Live source search is unavailable right now. Try the broader research link below; "
            "a failed search is not evidence about the claim."
        )
    else:
        summary = (
            "No related articles or recent headlines were found in these searches. "
            "That does not prove the claim true or false."
        )
    return combined, summary


def analyze_claim(claim: str) -> dict[str, object]:
    """Check common wording cues and retrieve related articles without assigning a verdict."""
    normalized = re.sub(r"\s+", " ", claim).strip()
    lowered = normalized.casefold()
    has_source_cue = re.search(
        r"https?://|www\.|\b(?:according to|source:|via|reuters|associated press|ap news|"
        r"factcheck\.org|snopes|full fact|who|cdc|nhs)\b|"
        r"\b[\w-]+\.(?:com|org|gov|edu|net|int)\b",
        lowered,
    )
    signals = (
        ["A source name or link appears in the selected text; check who published it and when."]
        if has_source_cue
        else ["No publisher, author, or source is included in the selected text."]
    )
    cue_groups = (
        (
            (r"\bforward(?:ed|ing)?\b", r"\bshare\b", r"\bsend\b", r"\bpass(?:ed|ing)?\s+(?:this|it)\s+on\b"),
            "It asks people to pass the message along; sharing pressure is a reason to pause, not proof it is false.",
        ),
        (
            (r"\b(?:urgent|immediately|right now|now|today|act now|breaking|before .* deleted)\b",),
            "It uses urgency or pressure to encourage a quick reaction.",
        ),
        (
            (r"\b(?:cure|heal|prevent|treat|detox|toxin|cancer|infection|virus|medicine)\w*\b",),
            "It makes a health-related claim; check qualified medical sources and the original evidence.",
        ),
        (
            (r"\b(?:guaranteed|everyone|nobody|never|always|all|every|100\s*%)\b",),
            "It uses sweeping or certainty-heavy words that may leave out important context.",
        ),
    )
    for patterns, signal in cue_groups:
        if any(re.search(pattern, lowered) for pattern in patterns):
            signals.append(signal)
    if len(signals) == 1:
        signals.append(
            "No common sharing-pressure or certainty wording stood out; that does not verify the claim."
        )
    sources, source_summary = _search_everywhere(normalized)
    query = _research_terms(normalized)
    trusted_sites = " OR ".join(f"site:{site}" for site in TRUSTED_RESEARCH_SITES)
    return {
        "claim": normalized,
        "signals": signals,
        "sources": sources,
        "source_summary": source_summary,
        "search_url": "https://www.google.com/search?q=" + quote_plus(f"{query} ({trusted_sites})"),
    }


def answer_followup(claim: str, question: str) -> dict[str, object]:
    claim_terms = _research_terms(claim).split()[:4]
    question_query = _research_terms(question)
    query = " ".join((question_query.split() + claim_terms)[:12])
    sources, summary = _search_google_news(query)
    if sources:
        answer = (
            f"I searched Google News for “{question}” in the context of the original message. "
            f"I found {len(sources)} related headline(s); the most recent result is “{sources[0]['title']}”"
            f"{' from ' + sources[0]['publisher'] if sources[0]['publisher'] else ''}. "
            "Headlines alone aren’t enough to establish the full answer, so open the linked reporting and check its evidence."
        )
    else:
        answer = (
            f"I couldn’t find related current headlines for “{question}”. {summary} "
            "I can’t answer that reliably from the available search results."
        )
    return {"answer": answer, "sources": sources}


class FakeNewsCheckerHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError as error:
            print(f"Client disconnected before the response could be sent ({type(error).__name__}).")

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path not in ("/api/analyze", "/api/ask"):
            self._send_json(404, {"error": "Not found."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid request length."})
            return
        if content_length < 1 or content_length > MAX_CLAIM_LENGTH * 4:
            self._send_json(413, {"error": "Message is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request must contain valid JSON."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request must be a JSON object."})
            return
        if self.path == "/api/analyze":
            text = payload.get("text")
            if not isinstance(text, str):
                self._send_json(400, {"error": "Include the message as a text field."})
                return
            claim = text.strip()
            if not claim:
                self._send_json(400, {"error": "Select or paste a message first."})
                return
            if len(claim) > MAX_CLAIM_LENGTH:
                self._send_json(413, {"error": "Message must be 4,000 characters or less."})
                return
            self._send_json(200, analyze_claim(claim))
            return

        claim = payload.get("claim")
        question = payload.get("question")
        if not isinstance(claim, str) or not isinstance(question, str):
            self._send_json(400, {"error": "Include the original claim and follow-up question."})
            return
        claim = claim.strip()
        question = question.strip()
        if not claim or not question:
            self._send_json(400, {"error": "The original claim and a question are both required."})
            return
        if len(claim) > MAX_CLAIM_LENGTH or len(question) > 500:
            self._send_json(413, {"error": "The claim must be at most 4,000 characters and the question at most 500."})
            return
        self._send_json(200, answer_followup(claim, question))

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), FakeNewsCheckerHandler)
    print(f"Fake News Checker is running at http://{HOST}:{PORT} (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Fake News Checker.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()