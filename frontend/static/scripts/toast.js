"use strict";

/**
 * Insert a toast message into the #toast-container element. Automatically fades out after durationMs.
 * @param {string} message Text to display in the toast 
 * @param {string} type Optional type for styling (i.e. "success", "error", "warning", "info"). Defaults to "info".
 *                          Maps to .toast-{type} CSS classes.
 * @param {string} durationMs How long the toast should be visible before fading out, in milliseconds. Defaults to 4000 (4 seconds).
 * @returns 
 */
function showToast(message, type = "info", durationMs = 4000) {
    const container = document.getElementById("toast-container");
    if (!container) {
        // #toast-container isn't on every page, fail silently if not found
        console.warn("#toast-container not found, skipping:", message, type);
        return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    // role="alert" for screen readers to announce immediately
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    container.appendChild(toast);

    // After durationMs, fade out and remove the toast
    setTimeout(() => {
        // Use CSS transitions for smooth fade-out and slide-up effect
        toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-8px)";

        // Remove the toast from the DOM after the transition completes
        setTimeout(() => toast.remove(), 320);
    }, durationMs);
}

// Expose globally so inline event handlers and other scripts can call showToast()
window.showToast = showToast;

/**
 * Channel 1: Flash cookie (used after HX-Redirect)
 * When an action (create/edit/delete event) ends with a redirect, HTMX navigates away
 * before any response body can be processed. The server sets two short-lived cookies
 * which this handler reads on the next page load, shows the toast,
 * and then immediately clears
 */
document.addEventListener("DOMContentLoaded", () => {
    /** @type {Record<string, string>} */
    const cookies = {};
    document.cookie.split(";").forEach(cookieStr => {
        const [rawKey, ...rawValueParts] = cookieStr.trim().split("=");
        const key = rawKey.trim();
        if (key) cookies[key] = decodeURIComponent(rawValueParts.join("="));
    });

    const message = cookies["flash_message"];
    const type = cookies["flash_type"] || "info";

    if (message) {
        showToast(message, type);
        // Clear the flash cookies immediately so they don't trigger again on the next page load
        document.cookie = "flash_message=; max-age=0; path=/; samesite=lax";
        document.cookie = "flash_type=; max-age=0; path=/; samesite=lax";
    }
});

/**
 * Channel 2: HX-Trigger "showToast" event (used for in-place HTMX swaps)
 * When an HTMX response includes `HX-Trigger: {"showToast": {"message": "...", "type": "..."}}`,
 * HTMX dispatches a custom "showToast" event on document.body. This is used for
 * RSVP add/remove actions which don't redirect but still want to show a toast notification.
 */
document.body.addEventListener("showToast", (e) => {
    const { message, type = "info" } = e.detail || {};
    if (message) showToast(message, type);
});

// Error toasts for HTMX HTTP errors
document.addEventListener("htmx:responseError", (e) => {
    const status = e.detail?.xhr?.status;
    let message = "An unexpected error occurred. Please try again";

    if (status === 401) {
        message = "You must be logged in to perform this action";
    } else if (status === 403) {
        message = "You don't have permission to perform this action";
    } else if (status === 404) {
        message = "The requested resource wasn't found";
    } else if (status === 422) {
        message = "Invalid input, please check the form data";
    } else if (status >= 500) {
        message = "A server error occurred, please try again later";
    }

    showToast(message, "error");
});

// Error toast for network errors
document.addEventListener("htmx:sendError", (e) => {
    showToast("Network error: Please check your internet connection", "error");
});