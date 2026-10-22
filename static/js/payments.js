/* Check an existing request only. This script never initiates a payment. */
document.querySelectorAll('form[data-payment-check]').forEach((form) => {
  const message = form.querySelector('[data-payment-check-message]');
  const token = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
  if (!token) return;
  let attempts = 0;
  const check = async () => {
    if (document.hidden) {
      window.setTimeout(check, 16000);
      return;
    }
    attempts += 1;
    try {
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin', redirect: 'error',
        headers: { 'X-CSRFToken': token, 'Accept': 'application/json' },
      });
      if (response.status === 403 || response.status === 404) {
        message.textContent = 'Sign in again to check this payment.';
        return;
      }
      if (response.ok) {
        const result = await response.json();
        message.textContent = result.message;
        if (result.status === 'success' || result.status === 'failed') {
          window.location.reload();
          return;
        }
      } else {
        message.textContent = 'Still waiting for confirmation. You can check again below.';
      }
    } catch {
      message.textContent = 'Unable to check right now. Your payment request has not been resent.';
    }
    if (attempts < 10) window.setTimeout(check, 16000);
    else message.textContent = 'Confirmation is taking longer than expected. Use Check payment status to try again.';
  };
  window.setTimeout(check, 16000);
});
