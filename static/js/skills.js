/* Optional local catalogue suggestions; manually entered skills remain valid. */
(() => {
  const list = document.querySelector('[data-skill-suggestions]');
  if (!list) return;
  const status = document.querySelector('[data-skill-search-status]');
  let timer;
  let controller;
  let sequence = 0;
  document.addEventListener('input', (event) => {
    if (!event.target.matches('[data-skill-input]')) return;
    const input = event.target;
    const query = input.value.trim();
    clearTimeout(timer);
    controller?.abort();
    const request = ++sequence;
    list.replaceChildren();
    if (query.length < 2 || query.length > 80) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const url = new URL(list.dataset.url, window.location.origin);
        url.searchParams.set('q', query);
        const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
        if (!response.ok) throw new Error('Suggestions unavailable');
        const data = await response.json();
        if (request !== sequence || document.activeElement !== input) return;
        const options = data.suggestions.map((suggestion) => {
          const option = document.createElement('option');
          option.value = suggestion.label;
          if (suggestion.matched_label !== suggestion.label) option.label = suggestion.matched_label;
          return option;
        });
        list.replaceChildren(...options);
        if (status) status.textContent = options.length ? `${options.length} skill suggestions available.` : 'No suggestions. You can keep your own wording.';
      } catch (error) {
        if (error.name !== 'AbortError' && request === sequence && status) status.textContent = 'Suggestions unavailable. You can still enter and save your skill.';
      }
    }, 250);
  });
})();
