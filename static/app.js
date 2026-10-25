const players = new WeakMap();

function showAd(article) {
  const ad = article.querySelector("[data-ad]");
  if (ad) ad.hidden = false;
}

function play(button) {
  const article = button.closest(".result");
  if (!article) return;
  const mount = article.querySelector("[data-player]");
  const videoId = button.dataset.video;
  if (!mount || !videoId) return;
  showAd(article);
  if (players.has(article)) {
    mount.hidden = false;
    return;
  }
  const frame = document.createElement("iframe");
  frame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0`;
  frame.title = button.dataset.title || "Vídeo de YouTube";
  frame.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
  frame.allowFullscreen = true;
  frame.loading = "lazy";
  mount.replaceChildren(frame);
  mount.hidden = false;
  players.set(article, frame);
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-play]");
  if (!button) return;
  event.preventDefault();
  play(button);
});

document.addEventListener("click", (event) => {
  const closeLink = event.target.closest("[data-close-window]");
  if (!closeLink) return;
  event.preventDefault();
  const fallback = closeLink.href;
  window.close();
  window.setTimeout(() => {
    if (!window.closed) window.location.href = fallback;
  }, 200);
});

const sessionHash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
const incomingToken = sessionHash.get("access_token");
if (incomingToken) {
  const body = new URLSearchParams({ access_token: incomingToken });
  fetch("/auth/session", { method: "POST", body })
    .then((response) => {
      if (!response.ok) throw new Error("session");
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      window.location.reload();
    })
    .catch(() => {
      window.location.href = "/login";
    });
}
