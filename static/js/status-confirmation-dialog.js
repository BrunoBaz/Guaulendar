document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("status-confirmation-dialog");
    const title = document.getElementById("status-confirmation-title");
    const message = document.getElementById("status-confirmation-message");
    const acceptButton = dialog?.querySelector("[data-accept-status-confirmation]");
    let pendingForm = null;
    let pendingAction = null;

    if (!(dialog instanceof HTMLDialogElement)) {
        return;
    }

    function openConfirmation({ form, action, heading, prompt, confirmLabel }) {
        pendingForm = form;
        pendingAction = action || null;
        title.textContent = heading;
        message.textContent = prompt;
        acceptButton.textContent = confirmLabel || "Confirmar";
        dialog.showModal();
    }

    document.querySelectorAll("[data-status-confirm]").forEach((button) => {
        button.addEventListener("click", () => {
            const form = document.getElementById(button.dataset.statusForm);
            if (!(form instanceof HTMLFormElement)) {
                console.error("No se encontró el formulario asociado a la confirmación de estado.");
                return;
            }
            openConfirmation({
                form,
                action: button.dataset.statusAction,
                heading: button.dataset.statusTitle,
                prompt: button.dataset.statusMessage,
                confirmLabel: button.dataset.statusConfirmLabel,
            });
        });
    });

    document.querySelectorAll("[data-confirm-inactive]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const activeControl = form.querySelector(form.dataset.confirmInactive);
            if (form.dataset.statusConfirmed === "true") {
                delete form.dataset.statusConfirmed;
                return;
            }
            if (activeControl?.checked === false) {
                event.preventDefault();
                openConfirmation({
                    form,
                    heading: form.dataset.statusTitle,
                    prompt: form.dataset.statusMessage,
                    confirmLabel: form.dataset.statusConfirmLabel,
                });
            }
        });
    });

    acceptButton?.addEventListener("click", () => {
        if (!pendingForm) {
            return;
        }
        if (pendingAction) {
            const actionInput = pendingForm.querySelector("[data-status-action-field]");
            if (!(actionInput instanceof HTMLInputElement)) {
                console.error("No se encontró el campo de acción para actualizar el estado.");
                return;
            }
            actionInput.value = pendingAction;
        }
        const formToSubmit = pendingForm;
        pendingForm = null;
        pendingAction = null;
        dialog.close();
        formToSubmit.dataset.statusConfirmed = "true";
        formToSubmit.requestSubmit();
    });

    dialog.querySelector("[data-cancel-status-confirmation]")?.addEventListener("click", () => {
        pendingForm = null;
        pendingAction = null;
        dialog.close();
    });
});
