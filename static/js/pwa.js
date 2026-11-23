// Registro del service worker: da soporte offline y permite instalar la app.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js", { scope: "/" });
    });
}
