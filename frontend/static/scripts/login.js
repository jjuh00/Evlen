"use strict";

/**
 * Activate one authentication tab panel and deactivates the other.
 * @param {string} name "login" or "register"
 */
function switchTab(name) {
    const panels = ["login", "register"];

    panels.forEach(id => {
        const button = document.getElementById(`tab-${id}`);
        const panel = document.getElementById(`panel-${id}`);
        const isActive = (id === name);

        // Flip CSS classes to show/hide panels and indicate active tab
        button.classList.toggle("tab-active", isActive);
        panel.classList.toggle("panel-active", isActive);

        // Update ARIA attributes for accessibility
        button.setAttribute("aria-selected", String(isActive));
    });
}

// Expose on window so the onclick handler attributes in the HTML can access it
window.switchTab = switchTab;

/**
 * On page load, check the URL query parameters for ?tab= and activate the corresponding tab.
 * Default to "login" if the parameter is missing or invalid.
 * This allows server-side redirects to specify which tab should be active after a form submission.
 */
document.addEventListener("DOMContentLoaded", function initTab() {
    const params = new URLSearchParams(window.location.search);
    const initialTab = params.get("tab") === "register" ? "register" : "login";
    switchTab(initialTab);
});