/* Progressive workspace navigation and a text-only job preview. */
(() => {
  document.querySelectorAll('[data-auto-submit]').forEach((select) => {
    const form = select.closest('form');
    if (!form) return;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.hidden = true;
    select.addEventListener('change', () => form.requestSubmit());
  });

  document.querySelectorAll('[data-section-nav]').forEach((nav) => {
    const layout = nav.closest('[data-section-layout]');
    if (!layout) return;
    const panels = [...layout.querySelectorAll('[data-section-panel]')];
    const links = [...nav.querySelectorAll('a[href^="#"]')];
    const activate = (id) => {
      if (!panels.some((panel) => panel.id === id)) return;
      panels.forEach((panel) => { panel.hidden = panel.id !== id; });
      links.forEach((link) => {
        if (link.hash === `#${id}`) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      });
    };
    const errorPanel = panels.find((panel) => panel.querySelector('.field-errors, .field-error'));
    const initial = errorPanel?.id || location.hash.slice(1) || panels[0]?.id;
    activate(panels.some((panel) => panel.id === initial) ? initial : panels[0]?.id);
    links.forEach((link) => link.addEventListener('click', () => activate(link.hash.slice(1))));
    window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
    layout.querySelectorAll('[data-form-errors] a[href^="#"]').forEach((link) => {
      link.addEventListener('click', () => activate(link.hash.slice(1)));
    });
  });

  document.querySelectorAll('[data-job-preview]').forEach((form) => {
    const value = (name) => form.elements.namedItem(name)?.value.trim() || '';
    const update = () => {
      const defaults = { title: 'Your job title', company: 'Your company', location: 'Location', description: 'Describe the role to see your preview.' };
      form.querySelectorAll('[data-preview]').forEach((element) => {
        element.textContent = value(element.dataset.preview) || defaults[element.dataset.preview];
      });
      const education = form.querySelector('[data-preview-education]');
      const level = form.elements.namedItem('education_level');
      if (education && level) education.textContent = [level.selectedOptions[0]?.textContent, value('education_field')].filter(Boolean).join(' · ');
      const experience = form.querySelector('[data-preview-experience]');
      const years = value('minimum_experience_years');
      if (experience) experience.textContent = years === '' ? 'No minimum specified' : `${years} ${Number(years) === 1 ? 'year' : 'years'} minimum`;
      const skills = form.querySelector('[data-preview-skills]');
      if (skills) {
        const chips = [...form.querySelectorAll('[data-profile-entry]')].flatMap((entry) => {
          const input = entry.querySelector('input[name$="-name"]');
          const removed = entry.querySelector('input[name$="-DELETE"]');
          if (!input?.value.trim() || removed?.checked) return [];
          const chip = document.createElement('span');
          chip.className = 'skill-chip';
          chip.textContent = input.value.trim();
          return [chip];
        });
        if (!chips.length) {
          const placeholder = document.createElement('p');
          placeholder.className = 'small-copy';
          placeholder.textContent = 'Add skills to preview them here.';
          chips.push(placeholder);
        }
        skills.replaceChildren(...chips);
      }
    };
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    update();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') document.querySelectorAll('.account-menu[open]').forEach((menu) => {
      menu.open = false;
      menu.querySelector('summary')?.focus();
    });
  });
})();
