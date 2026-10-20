/* Repeatable profile entries. Without JS, one new entry per section can be saved at a time. */
(() => {
  const status = document.querySelector('[data-entry-status]');
  document.querySelectorAll('[data-formset]').forEach((section) => {
    const prefix = section.dataset.formset;
    const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const list = section.querySelector('[data-entry-list]');
    const template = section.querySelector('[data-empty-entry]');
    const add = section.querySelector('[data-add-entry]');
    const limit = section.querySelector('[data-entry-limit]');
    if (!total || !list || !template || !add) return;
    const maximum = Number(section.dataset.maximum);
    const updateLimit = () => {
      const reached = Number(total.value) >= maximum;
      add.hidden = reached;
      limit.hidden = !reached;
    };
    updateLimit();
    add.addEventListener('click', () => {
      const index = Number(total.value);
      if (index >= maximum) return;
      const content = template.innerHTML.replaceAll('__prefix__', String(index));
      const row = document.createElement('template');
      row.innerHTML = content;
      const entry = row.content.firstElementChild;
      entry.querySelector('[data-entry-number]').textContent = String(index + 1);
      list.append(entry);
      total.value = String(index + 1);
      updateLimit();
      entry.querySelector('input:not([type="hidden"]), textarea, select')?.focus();
      if (status) status.textContent = `Added a new entry to ${section.querySelector('h2').textContent}.`;
    });
  });
})();
