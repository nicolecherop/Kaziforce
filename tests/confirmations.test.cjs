const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(process.env.CONFIRMATION_SCRIPT || path.join(__dirname, '..', 'static/js/confirmations.js'), 'utf8');

function setup({ dataset = {}, fields = {}, admin = false, bulk = false, decision = false } = {}) {
    class Form {
        method = 'post';
        constructor() {
            this.dataset = dataset;
            this.elements = { namedItem: name => fields[name] || null };
        }
        hasAttribute(name) { return Object.hasOwn(this.dataset, name.replace(/^data-/, '').replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())); }
        querySelector(selector) { return fields[selector] || null; }
        querySelectorAll() { return fields.actions || []; }
    }
    const form = new Form();
    const prompts = [];
    let handler;
    vm.runInNewContext(source, {
        HTMLFormElement: Form,
        WeakMap,
        document: {
            body: { classList: { contains: name => (admin && name === 'change-form') || (bulk && name === 'change-list') } },
            querySelectorAll: () => [form],
            addEventListener: (_, callback) => { handler = callback; },
        },
        window: { confirm: message => { prompts.push(message); return decision; } },
    });
    return { form, prompts, submit(value, buttonDataset = {}) {
        const event = { target: form, submitter: { value, dataset: buttonDataset }, prevented: false, stopped: false,
            preventDefault() { this.prevented = true; }, stopImmediatePropagation() { this.stopped = true; } };
        handler(event);
        return event;
    } };
}

test('cancelling completion prevents submission; accepting permits it', () => {
    for (const decision of [false, true]) {
        const page = setup({ dataset: { confirmBooking: '' }, decision });
        const event = page.submit('confirm_completion');
        assert.equal(event.prevented, !decision);
        assert.equal(event.stopped, !decision);
        assert.match(page.prompts[0], /completed.*payment/);
    }
});

test('the chosen button determines the decision in forms with multiple actions', () => {
    const page = setup();
    assert.equal(page.submit('draft').prevented, false);
    assert.equal(page.submit('submit', { confirm: 'Share this application?' }).prevented, true);
    assert.deepEqual(page.prompts, ['Share this application?']);
});

test('payment confirmation includes the entered amount and recipient; status checks do not prompt', () => {
    const page = setup({ dataset: { confirmPayment: '174379' }, fields: { amount: { value: '2500' } } });
    assert.equal(page.submit().prevented, true);
    assert.match(page.prompts[0], /KES 2500 to shortcode 174379/);
    const check = setup();
    assert.equal(check.submit().prevented, false);
    assert.equal(check.prompts.length, 0);
});

test('admin unchanged saves are quiet; granting admin access can be cancelled', () => {
    const fields = { is_staff: { type: 'checkbox', checked: false } };
    const page = setup({ admin: true, fields });
    assert.equal(page.submit('_save').prevented, false);
    fields.is_staff.checked = true;
    assert.equal(page.submit('_save').prevented, true);
    assert.match(page.prompts[0], /admin access/);
});

test('admin assigned permissions are checked even when Django moves them to another select', () => {
    const fields = { user_permissions: { multiple: true, selectedOptions: [{ value: '1' }] } };
    const page = setup({ admin: true, fields });
    fields['#id_user_permissions_to'] = { options: [{ value: '1' }] };
    assert.equal(page.submit('_save').prevented, false);
    fields['#id_user_permissions_to'].options.push({ value: '2' });
    assert.equal(page.submit('_save').prevented, true);
    assert.match(page.prompts[0], /account permissions/);
});

test('ordinary profile saves and GET requests remain unprompted', () => {
    const page = setup({ dataset: { confirm: 'Important decision?' } });
    page.form.method = 'get';
    assert.equal(page.submit().prevented, false);
    assert.equal(page.prompts.length, 0);
    assert.equal(setup().submit().prevented, false);
});

test('admin bulk actions prompt once; bulk deletion retains its existing review page', () => {
    const action = { value: 'approve', selectedOptions: [{ textContent: 'Approve selected records' }] };
    const page = setup({ bulk: true, fields: { actions: [{ value: '' }, action] } });
    assert.equal(page.submit().prevented, true);
    assert.match(page.prompts[0], /Approve selected records/);
    action.value = 'delete_selected';
    assert.equal(page.submit().prevented, false);
    assert.equal(page.prompts.length, 1);
});
