document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.dataset.confirm || "Are you sure?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll(".flash").forEach((flash) => {
        window.setTimeout(() => {
            flash.style.transition = "opacity 0.3s ease";
            flash.style.opacity = "0";

            window.setTimeout(() => flash.remove(), 350);
        }, 4000);
    });
});