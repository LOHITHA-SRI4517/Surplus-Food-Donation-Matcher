
document.addEventListener("DOMContentLoaded", () => {
    // Automatically hide flash messages after 6 seconds.
    const messages = document.querySelectorAll(
        ".flash-message, .alert"
    );

    messages.forEach((message) => {
        window.setTimeout(() => {
            message.style.transition = "opacity 0.5s ease";
            message.style.opacity = "0";

            window.setTimeout(() => {
                message.remove();
            }, 500);
        }, 6000);
    });

    // Ask for confirmation before collection or rejection actions.
    const confirmForms = document.querySelectorAll(
        "form[data-confirm]"
    );

    confirmForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message =
                form.getAttribute("data-confirm") ||
                "Are you sure you want to continue?";

            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });

    // Prevent accidental repeated clicks on submit buttons.
    const forms = document.querySelectorAll(
        "form[data-disable-submit]"
    );

    forms.forEach((form) => {
        form.addEventListener("submit", () => {
            const button = form.querySelector(
                'button[type="submit"], button:not([type])'
            );

            if (button) {
                button.disabled = true;
                button.textContent = "Please wait...";
            }
        });
    });
});
