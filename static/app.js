const players = new WeakMap();

async function loadAd(ad) {
  if (!ad) return;
  if (!ad.dataset.loaded) {
    ad.hidden = false;
    const rect = ad.getBoundingClientRect();
    const pageType = ad.dataset.pageType || "video_results";
    const payload = {
      application: "osap",
      page: {
        type: pageType,
        entity_type: ad.dataset.workId ? "work" : null,
        entity_id: ad.dataset.workId || null,
        language: document.documentElement.lang || "es",
      },
      placement: ad.dataset.adPlacement || "content_inline",
      device: window.innerWidth < 640 ? "mobile" : "desktop",
      mode: "auto_area",
      area: {
        width: Math.max(160, Math.min(2000, Math.round(rect.width))),
        height: Math.max(120, Math.min(1200, Math.round(rect.height))),
      },
      max_ads: 1,
      gap: 0,
      orientation: "auto",
    };
    try {
      const response = await fetch("/ads/compose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        const fragment = await response.text();
        if (fragment && !fragment.includes('data-layout-status="no-fill"')) {
          ad.innerHTML = fragment;
          ad.dataset.loaded = "1";
          return;
        }
      }
    } catch {
      // Se conserva el anuncio propio de respaldo.
    }
    ad.dataset.loaded = "1";
  }
  ad.hidden = false;
}

function showAd(article) {
  return loadAd(article.querySelector("[data-ad]"));
}

function showWideAd() {
  return loadAd(document.querySelector(".ad-slot.ad-wide"));
}

function play(button) {
  const article = button.closest(".result");
  if (!article) return;
  const mount = article.querySelector("[data-player]");
  const videoId = button.dataset.video;
  if (!mount || !videoId) return;
  void showAd(article);
  void showWideAd();
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
