/**
 * Удаление фона нейросетью (IS-Net через @imgly/background-removal 1.4.5,
 * собрана в vendor/bg-removal.js). Считается прямо на устройстве, фото
 * никуда не отправляются. Сама модель (≈44 или ≈88 МБ) и движок ONNX
 * скачиваются один раз при первом использовании, дальше лежат в кэше.
 */
import { state, saveSettings } from './store.js';

// Версия данных обязана совпадать с версией библиотеки в vendor/.
const SOURCES = [
  'https://staticimgly.com/@imgly/background-removal-data/1.4.5/dist/',
  'https://unpkg.com/@imgly/background-removal-data@1.4.5/dist/',
];

export const AI_MODELS = {
  small: { name: 'Быстрая', size: '≈ 55 МБ' },
  medium: { name: 'Точная', size: '≈ 100 МБ' },
};

let lib;
const load = async () => (lib ??= await import('../vendor/bg-removal.js'));

function config(onProgress) {
  return {
    model: AI_MODELS[state.settings.aiModel] ? state.settings.aiModel : 'small',
    output: { format: 'image/png' },
    progress: (key, current, total) => {
      onProgress?.(describe(key, current, total));
    },
  };
}

function describe(key, current, total) {
  if (key.startsWith('fetch:')) {
    const pct = total ? Math.round((current / total) * 100) : 0;
    return key.includes('/models/') ? `Скачиваю нейросеть… ${pct}%` : `Скачиваю движок… ${pct}%`;
  }
  return 'Нейросеть убирает фон…';
}

/** Перебирает источники модели: если первый недоступен, пробует следующий. */
async function withSources(run) {
  const preferred = state.settings.aiSource;
  const order = preferred ? [preferred, ...SOURCES.filter((s) => s !== preferred)] : SOURCES;
  let lastErr;
  for (const publicPath of order) {
    try {
      const res = await run(publicPath);
      if (state.settings.aiSource !== publicPath) saveSettings({ aiSource: publicPath });
      return res;
    } catch (e) {
      lastErr = e;
      console.warn('Нейросеть: источник недоступен', publicPath, e);
    }
  }
  throw new Error(navigator.onLine === false
    ? 'Нет интернета, а нейросеть ещё не скачана'
    : `Не удалось запустить нейросеть: ${lastErr?.message ?? lastErr}`);
}

/** Blob → Blob PNG с прозрачным фоном того же размера. */
export async function aiRemoveBackground(blob, onProgress) {
  const { removeBackground } = await load();
  return withSources((publicPath) => removeBackground(blob, { ...config(onProgress), publicPath }));
}

/** Скачать модель заранее (например, по Wi-Fi). */
export async function aiPreload(onProgress) {
  const { preload } = await load();
  await withSources((publicPath) => preload({ ...config(onProgress), publicPath }));
  await saveSettings({ aiReady: state.settings.aiModel || 'small' });
}
