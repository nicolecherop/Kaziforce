/* Confirm consequential submissions without changing server-side permissions. */
(() => {
    "use strict";

    const bookingMessages = {
        accept: "Are you sure you want to accept this booking? These dates will be reserved and your contact details shared with the recruiter.",
        confirm_completion: "Are you sure you want to confirm that the agreed work is complete? The booking will be marked completed and you will continue to payment.",
        request_completion: "Are you sure the agreed work is complete? The recruiter will be asked to confirm completion.",
        cancel: "Are you sure you want to withdraw this booking request?",
        decline: "Are you sure you want to decline this booking?",
        request_cancel: "Are you sure you want to request cancellation of this booking?",
        agree_cancel: "Are you sure you want to cancel this booking? Reserved dates will be released. Any refund must be arranged separately.",
        report_payment: "Are you sure you have already sent this payment or refund? A payment report will be sent to the recipient for confirmation.",
        review: "Are you sure you want to submit this review? Your rating will contribute to the freelancer's reputation.",
    };

    const adminFields = {
        is_active: "account activation",
        is_staff: "admin access",
        is_superuser: "full administrator permissions",
        role: "account role",
        groups: "access groups",
        user_permissions: "account permissions",
        permissions: "group permissions",
        status: "status",
        recruiter: "recruiter ownership",
        is_hidden: "review visibility",
        is_resolved: "report resolution",
        accepting_bookings: "booking availability",
    };
    const initialAdminValues = new WeakMap();

    function fieldValue(form, name) {
        // Django's permission widget moves assigned options into a second select.
        const assigned = form.querySelector(`#id_${name}_to`);
        if (assigned) return JSON.stringify(Array.from(assigned.options, option => option.value).sort());
        const field = form.elements.namedItem(name);
        if (!field) return null;
        if (field.type === "checkbox") return String(field.checked);
        if (field.multiple) return JSON.stringify(Array.from(field.selectedOptions, option => option.value).sort());
        return field.value;
    }

    function snapshotAdminForms() {
        if (!document.body.classList.contains("change-form")) return;
        document.querySelectorAll("#content-main form").forEach(form => {
            initialAdminValues.set(form, Object.fromEntries(
                Object.keys(adminFields).map(name => [name, fieldValue(form, name)])
            ));
        });
    }

    function confirmationMessage(form, button) {
        const explicit = button?.dataset.confirm || form.dataset.confirm;
        if (explicit) return explicit;
        if (form.hasAttribute("data-confirm-booking")) return bookingMessages[button?.value] || "";
        if (form.hasAttribute("data-confirm-payment")) {
            const amount = form.elements.namedItem("amount")?.value || "the entered amount";
            return `Are you sure you want to request an M-Pesa payment of KES ${amount} to shortcode ${form.dataset.confirmPayment}? Check the recipient and amount before approving the phone prompt.`;
        }
        const initial = initialAdminValues.get(form);
        if (initial) {
            const changed = Object.keys(adminFields).filter(name => initial[name] !== fieldValue(form, name));
            if (changed.length) return `Are you sure you want to save these changes: ${changed.map(name => adminFields[name]).join(", ")}? They take effect when you save.`;
        }
        if (document.body.classList.contains("change-list")) {
            const action = Array.from(form.querySelectorAll('select[name="action"]')).find(field => field.value);
            // Django provides a separate review page for bulk deletion.
            if (action?.value && action.value !== "delete_selected") {
                const label = action.selectedOptions?.[0]?.textContent.trim() || "this action";
                return `Are you sure you want to apply “${label}” to the selected records?`;
            }
        }
        return "";
    }

    snapshotAdminForms();
    document.addEventListener("submit", event => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") return;
        const message = confirmationMessage(form, event.submitter);
        if (message && !window.confirm(message)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
})();
