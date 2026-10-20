/**
 * Формы заявки: маска телефона, валидация, отправка без перезагрузки.
 * Без скрипта браузер отправит обычный POST и покажет ответ сервера.
 */
import { analytics, contacts, OPERATOR_CODES } from '../config/site';

const MIN_FILL_MS = 2500;

function digitsOf(value: string): string {
  let d = value.replace(/\D/g, '');
  if (d.startsWith('375')) d = d.slice(3);
  else if (d.startsWith('80')) d = d.slice(2);
  return d.slice(0, 9);
}

function formatPhone(value: string): string {
  const d = digitsOf(value);
  if (!d) return '';
  let out = `+375 (${d.slice(0, 2)}`;
  if (d.length >= 2) out += ')';
  if (d.slice(2, 5)) out += ` ${d.slice(2, 5)}`;
  if (d.slice(5, 7)) out += `-${d.slice(5, 7)}`;
  if (d.slice(7, 9)) out += `-${d.slice(7, 9)}`;
  return out;
}

function phoneError(value: string): string {
  const d = digitsOf(value);
  if (!d.length) return 'Укажите номер телефона';
  if (d.length < 9) return 'Номер неполный: нужно 9 цифр после +375';
  if (!(OPERATOR_CODES as readonly string[]).includes(d.slice(0, 2))) return `Код оператора: ${OPERATOR_CODES.join(', ')}`;
  return '';
}

function setError(form: HTMLFormElement, field: string, message: string) {
  const box = form.querySelector<HTMLElement>(`[data-error-for="${field}"]`);
  const input = form.querySelector<HTMLInputElement>(`[name="${field}"]`);
  if (box) box.textContent = message;
  input?.setAttribute('aria-invalid', message ? 'true' : 'false');
}

function status(form: HTMLFormElement, text: string, state: '' | 'ok' | 'error' = '') {
  const box = form.querySelector<HTMLElement>('[data-form-status]');
  if (!box) return;
  box.textContent = text;
  box.dataset.state = state;
}

export function reachGoal(goal: string) {
  const w = window as unknown as { ym?: (id: number, a: string, g: string) => void; gtag?: (...a: unknown[]) => void };
  try {
    if (analytics.yandexMetrika) w.ym?.(Number(analytics.yandexMetrika), 'reachGoal', goal);
    w.gtag?.('event', goal);
  } catch { /* аналитика не мешает заявке */ }
}

function initForm(form: HTMLFormElement) {
  const ts = form.querySelector<HTMLInputElement>('[data-ts]');
  if (ts) ts.value = String(Date.now());
  const phone = form.querySelector<HTMLInputElement>('[data-phone]');
  if (phone) {
    phone.addEventListener('input', () => {
      const atEnd = phone.selectionStart === phone.value.length;
      phone.value = formatPhone(phone.value);
      if (atEnd) phone.setSelectionRange(phone.value.length, phone.value.length);
      if (phone.getAttribute('aria-invalid') === 'true') setError(form, 'phone', '');
    });
    phone.addEventListener('focus', () => { if (!phone.value) phone.value = '+375 ('; });
    phone.addEventListener('blur', () => {
      if (!digitsOf(phone.value).length) phone.value = '';
      else setError(form, 'phone', phoneError(phone.value));
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = form.querySelector<HTMLInputElement>('[name="name"]');
    const consent = form.querySelector<HTMLInputElement>('[name="consent"]');
    let ok = true;
    if (name && name.value.trim().length < 2) { setError(form, 'name', 'Как к вам обращаться?'); ok = false; } else setError(form, 'name', '');
    if (phone) { const err = phoneError(phone.value); setError(form, 'phone', err); if (err) ok = false; }
    if (consent && !consent.checked) { status(form, 'Отметьте согласие на обработку данных: без него мы не сможем перезвонить.', 'error'); ok = false; }
    if (!ok) { form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(); return; }

    const started = Number(ts?.value ?? 0);
    if (started && Date.now() - started < MIN_FILL_MS) { status(form, 'Проверьте поля и отправьте ещё раз.', 'error'); return; }

    const button = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    const label = button?.textContent ?? '';
    if (button) { button.disabled = true; button.textContent = 'Отправляем…'; }
    status(form, '');
    try {
      const res = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(String(res.status));
      form.reset();
      if (ts) ts.value = String(Date.now());
      status(form, 'Заявка принята. Диспетчер перезвонит в течение 10 минут.', 'ok');
      reachGoal('lead_sent');
    } catch {
      status(form, `Не получилось отправить. Позвоните: ${contacts.phoneHuman}, ответим сразу.`, 'error');
    } finally {
      if (button) { button.disabled = false; button.textContent = label; }
    }
  });
}

document.querySelectorAll<HTMLFormElement>('[data-lead-form]').forEach(initForm);
document.querySelectorAll<HTMLAnchorElement>('a[href^="tel:"]').forEach((a) => a.addEventListener('click', () => reachGoal('phone_click')));
document.querySelectorAll<HTMLAnchorElement>('[data-goal]').forEach((a) => a.addEventListener('click', () => reachGoal(a.dataset.goal ?? 'messenger')));
