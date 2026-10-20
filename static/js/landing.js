/* Decorative video has no on-page controls; motion and data preferences still apply. */
(() => {
  const video = document.querySelector('[data-hero-video]');
  if (!video) return;

  const source = video.querySelector('source');
  const status = document.querySelector('[data-video-status]');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const saveData = navigator.connection?.saveData === true;
  let loaded = false;
  let failed = false;

  const shouldPlay = () => !motion.matches && !saveData && !document.hidden && !failed;
  const play = async () => {
    if (!shouldPlay()) return;
    if (!loaded) {
      source.src = source.dataset.src;
      video.load();
      loaded = true;
    }
    video.muted = true;
    try {
      await video.play();
    } catch {
      // Keep the poster if the browser blocks autoplay.
      video.classList.remove('is-playing');
    }
  };

  video.addEventListener('playing', () => {
    if (shouldPlay()) video.classList.add('is-playing');
    else video.pause();
  });

  const fail = () => {
    failed = true;
    video.pause();
    video.classList.remove('is-playing');
    if (status) status.textContent = 'Background video is unavailable. A still image is displayed.';
  };
  video.addEventListener('error', fail);
  source.addEventListener('error', fail);

  motion.addEventListener('change', () => {
    if (motion.matches) {
      video.pause();
      video.classList.remove('is-playing');
    } else play();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) video.pause();
    else play();
  });
  play();
})();
