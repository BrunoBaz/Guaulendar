document.addEventListener("DOMContentLoaded", () => {
    const openDogButton = document.getElementById("open-dog-dialog");
    const dogDialog = document.getElementById("dog-dialog");
    const dogForm = document.getElementById("dog-registration-form");
    const dogIdInput = document.getElementById("dog-id");
    const dogActionInput = document.getElementById("dog-action");
    const title = document.getElementById("dog-dialog-title");
    const saveButton = document.getElementById("save-dog-button");
    const deactivateButton = document.getElementById("deactivate-dog-button");
    const activeField = document.querySelector("[data-dog-active-field]");
    const ownersSelect = document.getElementById("id_owners");
    const selectedOwners = document.getElementById("dog-selected-owners");

    if (!(dogDialog instanceof HTMLDialogElement)) {
        return;
    }

    function renderSelectedOwners() {
        selectedOwners.replaceChildren();
        const selectedOptions = [...ownersSelect.selectedOptions];

        if (!selectedOptions.length) {
            const emptyMessage = document.createElement("span");
            emptyMessage.className = "dog-dialog__selected-owners-empty";
            emptyMessage.textContent = "No hay responsables seleccionados.";
            selectedOwners.append(emptyMessage);
            return;
        }

        selectedOptions.forEach((option) => {
            const tag = document.createElement("span");
            tag.className = "dog-dialog__selected-owner";

            const name = document.createElement("span");
            name.textContent = option.textContent.trim();

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "dog-dialog__remove-owner";
            removeButton.textContent = "Quitar";
            removeButton.setAttribute("aria-label", `Quitar a ${option.textContent.trim()}`);
            removeButton.addEventListener("click", () => {
                option.selected = false;
                ownersSelect.dispatchEvent(new Event("change", { bubbles: true }));
            });

            tag.append(name, removeButton);
            selectedOwners.append(tag);
        });
    }

    ownersSelect.addEventListener("change", renderSelectedOwners);
    renderSelectedOwners();

    function setEditMode(isEditing, isActive = true) {
        title.textContent = isEditing ? "Editar ficha" : "Registrar perro";
        saveButton.textContent = isEditing ? "Guardar cambios" : "Registrar perro";
        deactivateButton.hidden = !isEditing || !isActive;
        activeField.hidden = !isEditing;
    }

    function resetForCreate() {
        dogForm.reset();
        dogIdInput.value = "";
        dogActionInput.value = "";
        document.querySelectorAll("#id_owners option").forEach((option) => {
            option.selected = false;
        });
        renderSelectedOwners();
        setEditMode(false);
    }

    openDogButton?.addEventListener("click", () => {
        resetForCreate();
        dogDialog.showModal();
    });

    document.querySelectorAll("[data-edit-dog]").forEach((button) => {
        button.addEventListener("click", () => {
            dogForm.reset();
            dogIdInput.value = button.dataset.editDog;
            dogActionInput.value = "";
            dogForm.elements.namedItem("name").value = button.dataset.name;
            dogForm.elements.namedItem("breed").value = button.dataset.breed;
            dogForm.elements.namedItem("color").value = button.dataset.color;
            dogForm.elements.namedItem("sex").value = button.dataset.sex;
            dogForm.elements.namedItem("coat_type").value = button.dataset.coatType;
            dogForm.elements.namedItem("dog_notes").value = button.dataset.notes;
            dogForm.elements.namedItem("dog_issues").value = button.dataset.issues;
            dogForm.elements.namedItem("is_active").checked = button.dataset.active === "true";
            const ownerIds = [...button.closest(".dog-card").querySelectorAll("[data-dog-owner-id]")]
                .map((owner) => owner.dataset.dogOwnerId);
            document.querySelectorAll("#id_owners option").forEach((option) => {
                option.selected = ownerIds.includes(option.value);
            });
            renderSelectedOwners();
            setEditMode(true, button.dataset.active === "true");
            dogDialog.showModal();
        });
    });

    if (dogDialog.dataset.openOnLoad === "true") {
        const isEditing = Boolean(dogIdInput.value);
        setEditMode(isEditing, dogForm.elements.namedItem("is_active").checked);
        dogDialog.showModal();
    }
});
