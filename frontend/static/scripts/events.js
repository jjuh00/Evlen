"use strict";

/**
 * Add a new empty schedule row to the given schedule row.
 * @param {string} listId - The `id` of the <ol> that holds the schedule rows.
 */
function addScheduleRow(listId) {
    const list = document.getElementById(listId);
    if (!list) return;

    // Read and increment the running index stored on the list element
    const index = parseInt(list.dataset.nextIndex ?? "0", 10);
    list.dataset.nextIndex = String(index + 1);

    const li = document.createElement("li");
    li.className = "schedule-row";
    li.dataset.index = String(index);

    li.innerHTML = `
        <input 
            class="input schedule-time"
            type="text"
            name="schedule-time-${index}"
            placeholder="Time"
            maxLength="25"
            aria-label="Schedule time ${index + 1}"
        >

        <input
            class="input schedule-description"
            type="text"
            name="schedule-description-${index}"
            placeholder="What happens at this time?"
            maxLength="200"
            aria-label="Schedule description ${index + 1}"
        >

        <button
            type="button"
            class="button button-secondary remove-schedule-row"
            aria-label="Remove schedule row ${index + 1}"
            onclick="removeScheduleRow(this)"
        >
            x
        </button>
    `;

    list.appendChild(li);

    // Focus the time input of the newly added row
    li.querySelector(".schedule-time").focus();
}

/**
 * Remove the schedule row that contains the given remove-button element.
 * @param {HTMLButtonElement} button - The remove-button inside the row to be removed.
 */
function removeScheduleRow(button) {
    const row = button.closest(".schedule-row");
    if (!row) return;
    row.remove();
}

// Expose schedule functions on window so inline onclick handlers in Jinja2 templates can reach them
window.addScheduleRow = addScheduleRow;
window.removeScheduleRow = removeScheduleRow;

/**
 * Activate a tag filter button aand deactivate all others.
 * Sets data-active="true" so the search input's hx-include can pick it up.
 * @param {HTMLButtonElement} button - The button that was clicked.
 */
function setTagFilter(button) {
    // Deactivate all tag filter buttons
    document.querySelectorAll("#tag-filter .tag-button").forEach(btn => {
        btn.dataset.active = "false";
        btn.classList.remove("tag-button--active");
    });

    // Activate the clicked button
    button.dataset.active = "true";
    button.classList.add("tag-button--active");
}

/**
 * Clear any active tag filter (active the "All" button).
 * @param {HTMLButtonElement} button - The "All" button that was clicked.
 */
function clearTagFilter(button) {
    // Deactivate all tag filter buttons, including the "All" button itself
    document.querySelectorAll("#tag-filter .tag-button").forEach(btn => {
        btn.dataset.active = "false";
        btn.classList.remove("tag-button--active");
    });

    // Activate the "All" button
    button.dataset.active = "true";
    button.classList.add("tag-button--active");
}

// Expose tag filter functions on window so inline onclick handlers in Jinja2 templates can reach them
window.setTagFilter = setTagFilter;
window.clearTagFilter = clearTagFilter;

/**
 * After a successful event creation (POST /events), clear the forms fields
 * and collapse the form section.
 * 
 * Success is detected by checking that the HX-Redirect response header is present.
 */
document.addEventListener("htmx:afterRequest", (e) => {
    const xhr = e.detail.xhr;
    if (!xhr) return;

    const redirectHeader = xhr.getResponseHeader("HX-Redirect");
    const form = e.detail.elt?.closest(".event-form");

    if (redirectHeader && form && form.id === "event-form") {
        // Reset all fields in the form
        form.reset();

        // Remove all dynamically added schedule rows
        const scheduleList = form.querySelector("#schedule-rows");
        if (scheduleList) {
            scheduleList.innerHTML = "";
            scheduleList.dataset.nextIndex = "0";
        }
    }
});