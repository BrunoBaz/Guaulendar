document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("contact-dialog");
    const saveButton = document.getElementById("save-contact-dialog");
    const nameInput = dialog?.querySelector("#contact-name");
    const phoneInput = dialog?.querySelector("#contact-phone");
    const form = dialog?.querySelector("#contact-registration-form");
    const contactIdInput = dialog?.querySelector("#contact-id");
    const contactActionInput = dialog?.querySelector("#contact-action");
    const title = dialog?.querySelector("#contact-dialog-title");
    const descartableInput = dialog?.querySelector('[name="descartable"]');

    if (!(dialog instanceof HTMLDialogElement)) {
        return;
    }

    if (dialog.dataset.openOnLoad === "true" && dialog.dataset.contactMode !== "dog") {
        dialog.showModal();
    }

    function openForCreate() {
        if (dialog.dataset.contactMode === "dog") {
            nameInput.value = document.getElementById("id_new_owner_name").value;
            phoneInput.value = document.getElementById("id_new_owner_phone").value;
            saveButton.textContent = saveButton.dataset.labelDog;
        } else {
            form.reset();
            contactIdInput.value = "";
            contactActionInput.value = "";
            title.innerHTML = 'Añadir <span>contacto</span>';
            saveButton.textContent = "Guardar contacto";
        }
        dialog.showModal();
    }

    document.getElementById("open-contact-dialog")?.addEventListener("click", openForCreate);
    document.querySelectorAll("[data-open-contact-dialog]").forEach((openButton) => {
        openButton.addEventListener("click", openForCreate);
    });

    document.querySelectorAll("[data-edit-contact]").forEach((button) => {
        button.addEventListener("click", () => {
            nameInput.value = button.dataset.name;
            phoneInput.value = button.dataset.phone;
            descartableInput.checked = button.dataset.descartable === "true";
            contactIdInput.value = button.dataset.editContact;
            contactActionInput.value = "edit";
            title.innerHTML = 'Editar <span>contacto</span>';
            saveButton.textContent = "Guardar cambios";
            dialog.showModal();
        });
    });

    dialog.querySelectorAll("[data-close-contact-dialog]").forEach((closeButton) => {
        closeButton.addEventListener("click", () => dialog.close());
    });

    if (dialog.dataset.contactMode !== "dog" || !saveButton || !nameInput || !phoneInput) {
        return;
    }

    saveButton.addEventListener("click", () => {
        const ownerName = nameInput.value.trim();
        const ownerPhone = phoneInput.value.trim();

        if (!ownerName) {
            nameInput.setCustomValidity("Escribe el nombre del cliente.");
            nameInput.reportValidity();
            nameInput.setCustomValidity("");
            return;
        }

        if (!ownerPhone) {
            phoneInput.setCustomValidity("Escribe el teléfono del cliente.");
            phoneInput.reportValidity();
            phoneInput.setCustomValidity("");
            return;
        }

        document.getElementById("id_new_owner_name").value = ownerName;
        document.getElementById("id_new_owner_phone").value = ownerPhone;

        const summary = document.getElementById("new-owner-summary");
        summary.textContent = `Se añadirá ${ownerName} (${ownerPhone}) al registrar el perro.`;
        summary.hidden = false;
        dialog.close();
    });
});
