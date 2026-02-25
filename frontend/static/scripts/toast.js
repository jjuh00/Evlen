"use strict";

/**
 * Insert a toast message into the #toast-container element. Automatically fades out after durationMs.
 * @param {string} message Text to display in the toast 
 * @param {string} type Optional type for styling (i.e. "success", "error", "warning", "info"). Defaults to "info".
 *                          Maps to .toast-{type} CSS classes.
 * @param {*} durationMs How long the toast should be visible before fading out, in milliseconds. Defaults to 3000 (3 seconds).
 * @returns 
 */
function showToast(message, type = "info", durationMs = 3000) {
    const container = document.getElementById("toast-container");
    if (!container) return; // Might not exist on all pages, silently fail if not found

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    // role="alert" for screen readers to announce immediately
    toast.setAttribute("role", "alert");
    container.appendChild(toast);

    // After durationMs, fade out and remove the toast
    setTimeout(() => {
        // Use CSS transitions for smooth fade-out and slide-up effect
        toast.style.transition = "opacity 0.3s transform 0.3s";
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-8px)";

        // Remove the toast from the DOM after the transition completes
        setTimeout(() => toast.remove(), 320);
    }, durationMs);
}

window.showToast = showToast; // Make globally accessible

/**
 * Post-process HTMX response for #health-result to pretty-print JSON if applicable.
 */
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

/**
 * Listen for HTMX response errors and show a toast notification with the error status.
 */
document.addEventListener("htmx:responseError", (e) => {
    const status = e.detail.xhr?.status;
    showToast(`Request failed: ${status ?? "unknown error occurred"}`, "error");
});

/**
 * Listen for HTMX send errors (e.g. network issues) and show a toast notification.
 */
document.addEventListener("htmx:sendError", () => {
    showToast("Network error: failed to send request", "error");
});