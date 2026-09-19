// Admin User Management dynamic interactions
document.addEventListener("DOMContentLoaded", () => {
    // Retrieve CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    // Attach listener to status toggle forms/buttons
    document.querySelectorAll(".status-toggle-form").forEach(form => {
        form.addEventListener("submit", async (e) => {
            const isDeactivating = form.dataset.action === "deactivate";
            const confirmMsg = isDeactivating
                ? "Are you sure you want to deactivate this account? The user will no longer be able to log in."
                : "Are you sure you want to reactivate this account?";

            if (!confirm(confirmMsg)) {
                e.preventDefault();
            }
        });
    });
});
