/* Shared progressive enhancements. Forms and role selection work without JS. */
document.querySelectorAll('[data-password-target]').forEach((button) => {
  const field = document.getElementById(button.dataset.passwordTarget);
  if (!field) return;
  button.addEventListener('click', () => {
    const reveal = field.type === 'password';
    field.type = reveal ? 'text' : 'password';
    field.toggleAttribute('data-revealed', reveal);
    button.setAttribute('aria-pressed', String(reveal));
    const label = document.querySelector(`label[for="${field.id}"]`);
    button.setAttribute('aria-label', `${reveal ? 'Hide' : 'Show'} ${(label?.textContent || 'password').replace(':', '').toLowerCase()}`);
  });
});

document.querySelector('[data-form-errors]')?.focus();

// Scheduling calendars use the site's date, rather than the browser's timezone.
document.querySelectorAll('input[data-date-floor]').forEach((start) => {
  const end = start.form?.elements.namedItem(start.dataset.rangeEnd || '');
  const sync = () => {
    const parts = new Intl.DateTimeFormat('en', {
      timeZone: start.dataset.dateTimezone, year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date());
    const value = (type) => parts.find((part) => part.type === type).value;
    const today = `${value('year')}-${value('month')}-${value('day')}`;
    const floor = today > start.dataset.dateFloor ? today : start.dataset.dateFloor;
    start.min = floor;
    if (end) end.min = start.value > floor ? start.value : floor;
  };
  ['input', 'change', 'focus'].forEach((event) => start.addEventListener(event, sync));
  end?.addEventListener('focus', sync);
  sync();
});
