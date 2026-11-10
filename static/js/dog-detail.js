document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("dog-appointment-dialog");
    const openButton = document.getElementById("open-dog-appointment-dialog");
    const editDialog = document.getElementById("dog-edit-dialog");
    const openEditButton = document.getElementById("open-dog-edit-dialog");

    if (dialog instanceof HTMLDialogElement) {
        openButton?.addEventListener("click", () => dialog.showModal());
        dialog.querySelectorAll("[data-close-dog-appointment]").forEach((button) => {
            button.addEventListener("click", () => dialog.close());
        });

        if (dialog.dataset.openOnLoad === "true") {
            dialog.showModal();
        }
    }

    if (!(editDialog instanceof HTMLDialogElement)) {
        return;
    }

    openEditButton?.addEventListener("click", () => editDialog.showModal());
    editDialog.querySelectorAll("[data-close-dog-edit-dialog]").forEach((button) => {
        button.addEventListener("click", () => editDialog.close());
    });

    if (editDialog.dataset.openOnLoad === "true") {
        editDialog.showModal();
    }
});
