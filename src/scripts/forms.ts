/**
 * Поведение форм заявки: маска телефона, валидация, отправка без перезагрузки.
 *
 * Разметка формы самодостаточна: без этого скрипта браузер отправит обычный
 * POST на тот же адрес и покажет ответ сервера. Скрипт только делает процесс
 * приятнее — это прогрессивное улучшение, а не условие работоспособности.
 */

import { analytics } from '../config/site';

const OPERATOR_CODES = ['25', '29', '33', '44'];
const MIN_FILL_MS = 3000;

/** Оставляет от введённого только значимые цифры национального номера. */
function digitsOf(value: string): string {
  let d = value.replace(/\D/g, '');
  if (d.startsWith('375')) d = d.slice(3);
  else if (d.startsWith('80')) d = d.slice(2);
  return d.slice(0, 9);
}

function formatPhone(value: string): string {
  const d = digitsOf(value);
  if (!d) return '';
  const code = d.slice(0, 2);
  const a = d.slice(2, 5);
  const b = d.slice(5, 7);
  const c = d.slice(7, 9);
  let out = `+375 (${code}`;
  if (d.length >= 2) out += ')';
  if (a) out += ` ${a}`;
  if (b) out += `-${b}`;
  if (c) out += `-${c}`;
  return out;
}

function phoneError(value: string): string {
  const d = digitsOf(value);
  if (d.length === 0) return 'Укажите номер телефона';
  if (d.length < 9) return 'Номер неполный — нужно 9 цифр после +375';
  if (!OPERATOR_CODES.includes(d.slice(0, 2))) {
    return `Код оператора должен быть ${OPERATOR_CODES.join(', ')}`;
  }
  return '';
}

function setError(form: HTMLFormElement, field: string, message: string) {
  const box = form.querySelector<HTMLElement>(`[data-error-for="${field}"]`);
  const input = form.querySelector<HTMLInputElement>(`[name="${field}"]`);
  if (box) box.textContent = message;
  if (input) input.setAttribute('aria-invalid', message ? 'true' : 'false');
}

function status(form: HTMLFormElement, text: string, state: '' | 'ok' | 'error' = '') {
  const box = form.querySelector<HTMLElement>('[data-form-status]');
  if (!box) return;
  box.textContent = text;
  box.dataset.state = state;
}

/**
 * Цель в счётчиках: вызывается на успешной отправке и на клике по телефону.
 *
 * Номер счётчика берём из конфига — того же, из которого его подставляет
 * Base.astro. Вытаскивать его из внутренностей window.Ya._metrika нельзя:
 * счётчики лежат там под ключами вида counter102469598, и Number() от такого
 * ключа даёт NaN, то есть цель уходит в никуда.
 */
function reachGoal(goal: string) {
  const w = window as unknown as {
    ym?: (id: number, action: string, target: string) => void;
    gtag?: (...args: unknown[]) => void;
  };
  try {
    // Заглушка ym появляется сразу и копит вызовы до загрузки tag.js,
    // так что цель не потеряется, даже если кликнули в первую секунду.
    if (analytics.yandexMetrika) {
      w.ym?.(Number(analytics.yandexMetrika), 'reachGoal', goal);
    }
    w.gtag?.('event', goal);
  } catch {
    /* аналитика не должна мешать отправке заявки */
  }
}

function initForm(form: HTMLFormElement) {
  const tsField = form.querySelector<HTMLInputElement>('[data-ts]');
  if (tsField) tsField.value = String(Date.now());

  const phone = form.querySelector<HTMLInputElement>('[data-phone]');
  if (phone) {
    phone.addEventListener('input', () => {
      const atEnd = phone.selectionStart === phone.value.length;
      phone.value = formatPhone(phone.value);
      if (atEnd) phone.setSelectionRange(phone.value.length, phone.value.length);
      if (phone.getAttribute('aria-invalid') === 'true') setError(form, 'phone', '');
    });
    phone.addEventListener('focus', () => {
      if (!phone.value) phone.value = '+375 (';
    });
    phone.addEventListener('blur', () => {
      if (digitsOf(phone.value).length === 0) phone.value = '';
      else setError(form, 'phone', phoneError(phone.value));
    });
  }

  form.addEventListener('submit', async (e) => {
    const name = form.querySelector<HTMLInputElement>('[name="name"]');
    const consent = form.querySelector<HTMLInputElement>('[name="consent"]');

    let ok = true;
    if (name && name.value.trim().length < 2) {
      setError(form, 'name', 'Как к вам обращаться?');
      ok = false;
    } else {
      setError(form, 'name', '');
    }

    if (phone) {
      const err = phoneError(phone.value);
      setError(form, 'phone', err);
      if (err) ok = false;
    }

    if (consent && !consent.checked) {
      status(form, 'Нужно согласие на обработку данных — без него мы не можем перезвонить.', 'error');
      ok = false;
    }

    if (!ok) {
      e.preventDefault();
      form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      return;
    }

    // Дальше отправляем сами, поэтому обычный сабмит останавливаем.
    e.preventDefault();

    const started = Number(tsField?.value ?? 0);
    if (started && Date.now() - started < MIN_FILL_MS) {
      status(form, 'Слишком быстро — проверьте, что поля заполнены верно.', 'error');
      return;
    }

    const button = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    const original = button?.textContent ?? '';
    if (button) {
      button.disabled = true;
      button.textContent = 'Отправляем…';
    }
    status(form, '');

    try {
      const res = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'application/json' },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      form.reset();
      if (tsField) tsField.value = String(Date.now());
      status(form, 'Заявка принята. Перезвоним в рабочее время — Пн–Сб с 09:00 до 19:00.', 'ok');
      reachGoal('lead_sent');
    } catch {
      status(
        form,
        'Не получилось отправить. Позвоните нам: +375 25 987-10-10 — ответим сразу.',
        'error',
      );
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  });
}

document.querySelectorAll<HTMLFormElement>('[data-lead-form]').forEach(initForm);

// Клик по телефону — тоже конверсия, её стоит считать.
document.querySelectorAll<HTMLAnchorElement>('a[href^="tel:"]').forEach((a) => {
  a.addEventListener('click', () => reachGoal('phone_click'));
});
