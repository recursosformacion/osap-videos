const players = new WeakMap();

function play(button) {
  const article = button.closest(".result");
  if (!article) return;
  const mount = article.querySelector("[data-player]");
  const videoId = button.dataset.video;
  if (!mount || !videoId) return;
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
