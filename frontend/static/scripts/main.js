// Toast helper
function showToast(message, type = "info", durationMs = 3000) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = "opacity 0.3s transform 0.3s";
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-8px)";
        setTimeout(() => toast.remove(), 320);
    }, durationMs);
}

// Format /health JSON response inline
document.addEventListener("htmx:afterSwap", (e) => {
    if (e.target.id === "health-result") {
        try {
            const parsed = JSON.parse(e.target.textContent);
            e.target.textContent = JSON.stringify(parsed, null, 2);
        } catch (error) {
            // Not JSON, leave as-is
        }
    }
});

// Global HTMX error handler -> toast
document.addEventListener("htmx:responseError", (e) => {
    const status = e.detail.xhr?.status;
    showToast(`Request failed: ${status ?? "unknown error occurred"}`, "error");
});