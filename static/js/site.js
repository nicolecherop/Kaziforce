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
