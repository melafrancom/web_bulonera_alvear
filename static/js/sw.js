// Service Worker para Bulonera Alvear PWA
// Estrategia: Cache First para assets, Network First para HTML, Network Only para API/Admin

const CACHE_NAME = 'bulonera-v1';
const STATIC_ASSETS = [
    '/',
    '/store/',
    '/offline/',
];

// Install: pre-cache assets críticos
self.addEventListener('install', event => {
    console.log('[SW] Installing Service Worker...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .catch(err => console.error('[SW] Cache addAll failed:', err))
    );
    self.skipWaiting();
});

// Activate: limpiar caches viejas
self.addEventListener('activate', event => {
    console.log('[SW] Activating Service Worker...');
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k !== CACHE_NAME)
                    .map(k => {
                        console.log('[SW] Deleting old cache:', k);
                        return caches.delete(k);
                    })
            )
        )
    );
    self.clients.claim();
});

// Fetch: estrategia por URL
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // API y admin: siempre red (Network Only)
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/')) {
        return; // fetch normal, sin intervención del SW
    }

    // Assets estáticos: Cache First
    if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
        event.respondWith(
            caches.match(request).then(cached => {
                if (cached) {
                    return cached;
                }
                return fetch(request).then(response => {
                    // Solo cachear respuestas exitosas
                    if (response && response.status === 200) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    }
                    return response;
                }).catch(err => {
                    console.error('[SW] Fetch failed for static asset:', url.pathname, err);
                    throw err;
                });
            })
        );
        return;
    }

    // HTML: Network First con fallback offline
    event.respondWith(
        fetch(request)
            .then(response => {
                // Cachear respuestas HTML exitosas
                if (response && response.status === 200 && response.headers.get('content-type')?.includes('text/html')) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                }
                return response;
            })
            .catch(() => {
                // Si falla la red, intentar caché
                return caches.match(request).then(cached => {
                    if (cached) {
                        return cached;
                    }
                    // Si no hay caché, mostrar página offline
                    return caches.match('/offline/');
                });
            })
    );
});
