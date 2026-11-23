{% load static %}/* Service worker de Guaulendar.
   Se sirve desde la raíz (/sw.js) para poder controlar toda la aplicación. */
const VERSION = "{{ asset_version }}";
const CACHE_NAME = `guaulendar-${VERSION}`;
const STATIC_PREFIX = "{% get_static_prefix %}";
const OFFLINE_URL = "{% url 'offline' %}";
const PRECACHE_URLS = [
    OFFLINE_URL,
    "{% static 'css/style.css' %}",
    "{% static 'js/pwa.js' %}",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) =>
                Promise.all(
                    keys
                        .filter((key) => key !== CACHE_NAME)
                        .map((key) => caches.delete(key))
                )
            )
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    // Solo se cachean lecturas: los formularios y la sesión van siempre a la red.
    if (request.method !== "GET") {
        return;
    }
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }

    // Pantallas: primero la red; sin conexión, el aviso offline. El HTML no se
    // guarda porque contiene los datos privados de cada negocio.
    if (request.mode === "navigate") {
        event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
        return;
    }

    // Recursos estáticos: caché primero, revalidando en segundo plano.
    if (url.pathname.startsWith(STATIC_PREFIX)) {
        event.respondWith(
            caches.match(request).then((cached) => {
                const network = fetch(request)
                    .then((response) => {
                        if (response && response.status === 200) {
                            const copy = response.clone();
                            caches
                                .open(CACHE_NAME)
                                .then((cache) => cache.put(request, copy));
                        }
                        return response;
                    })
                    .catch(() => cached);
                return cached || network;
            })
        );
    }
});
