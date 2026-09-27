const DB_NAME = 'fits';
const VERSION = 1;
export const STORES = ['items', 'outfits', 'plans', 'lookbooks', 'meta'];

let dbPromise;

export function openDB() {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('items')) db.createObjectStore('items', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('outfits')) db.createObjectStore('outfits', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('plans')) db.createObjectStore('plans', { keyPath: 'date' });
      if (!db.objectStoreNames.contains('lookbooks')) db.createObjectStore('lookbooks', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function run(stores, mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(stores, mode);
    let result;
    const req = fn(tx);
    if (req) req.onsuccess = () => { result = req.result; };
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error ?? new Error('Транзакция прервана'));
  });
}

export const getAll = (store) => run(store, 'readonly', (tx) => tx.objectStore(store).getAll());
export const get = (store, key) => run(store, 'readonly', (tx) => tx.objectStore(store).get(key));
export const put = (store, value) => run(store, 'readwrite', (tx) => tx.objectStore(store).put(value));
export const del = (store, key) => run(store, 'readwrite', (tx) => tx.objectStore(store).delete(key));

/** Несколько изменений в разных хранилищах одной транзакцией. ops: [{store, put}|{store, del}] */
export function batch(ops) {
  const stores = [...new Set(ops.map((o) => o.store))];
  if (!stores.length) return Promise.resolve();
  return run(stores, 'readwrite', (tx) => {
    for (const o of ops) {
      const s = tx.objectStore(o.store);
      if ('del' in o) s.delete(o.del);
      else s.put(o.put);
    }
  });
}

export const clearAll = () => run(STORES, 'readwrite', (tx) => { STORES.forEach((s) => tx.objectStore(s).clear()); });
