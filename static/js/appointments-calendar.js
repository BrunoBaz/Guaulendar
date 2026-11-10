document.addEventListener("DOMContentLoaded", () => {
    const calendarElement = document.getElementById("appointments-calendar");
    const eventsElement = document.getElementById("appointment-calendar-data");
    const dialog = document.getElementById("appointment-dialog");
    const createDialog = document.getElementById("appointment-create-dialog");
    const completionDialog = document.getElementById("appointment-completion-dialog");
    const appointmentForm = createDialog?.querySelector(".appointment-create-dialog__form");
    const quickStatusForm = document.getElementById("appointment-quick-status-form");
    const quickStatusAppointmentId = document.getElementById("quick-status-appointment-id");
    const quickStatusInput = document.getElementById("quick-status-value");

    if (!calendarElement || !eventsElement || !window.FullCalendar) {
        return;
    }

    const events = JSON.parse(eventsElement.textContent);
    const filterInput = document.getElementById("appointments-filter");
    const filterCount = document.getElementById("appointments-filter-count");
    const filterOptions = document.getElementById("appointments-filter-options");
    const clearFilterButton = document.getElementById("clear-appointments-filter");
    const dateFormatter = new Intl.DateTimeFormat("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
    });
    const timeFormatter = new Intl.DateTimeFormat("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });

    const dateInput = createDialog?.querySelector('input[name="date"]');
    const dogSelect = createDialog?.querySelector('select[name="dog"]');
    const statusInput = createDialog?.querySelector('select[name="status"]');
    const paymentMethodInput = createDialog?.querySelector('input[name="payment_method"]');
    const paymentMethodChoice = document.getElementById("appointment-payment-method-choice");
    const priceInput = createDialog?.querySelector('input[name="price"]');
    const discountsInput = createDialog?.querySelector('input[name="discounts_json"]');
    const appointmentIdInput = createDialog?.querySelector('input[name="appointment_id"]');
    const originalStatusInput = createDialog?.querySelector('input[name="original_status"]');
    const statusField = createDialog?.querySelector('[data-appointment-field="status"]');
    const appointmentTitle = document.getElementById("appointment-create-dialog-title");
    const saveAppointmentButton = document.getElementById("save-appointment");
    const discountRows = document.getElementById("appointment-discount-rows");
    const selectedAppointmentButton = document.getElementById("edit-appointment-button");
    const calendarTimezone = calendarElement.dataset.timezone;
    const mobileCalendarQuery = window.matchMedia("(max-width: 600px)");
    let selectedEvent = null;
    let dogSearch = null;
    let lastNonCompletedStatus = originalStatusInput?.value || statusInput?.value || "PENDING";
    let previousStatus = lastNonCompletedStatus;
    let completionConfirmed = false;

    function setupDogSearch() {
        const dogSelect = createDialog?.querySelector(".appointment-dog-select");
        if (!dogSelect) {
            return;
        }

        const wrapper = document.createElement("div");
        wrapper.className = "appointment-dog-search";
        const searchInput = document.createElement("input");
        const listbox = document.createElement("div");
        const label = createDialog.querySelector(`label[for="${dogSelect.id}"]`);

        searchInput.id = `${dogSelect.id}-search`;
        searchInput.type = "search";
        searchInput.className = "appointment-create-dialog__input";
        searchInput.placeholder = "Selecciona o busca perro o responsable";
        searchInput.autocomplete = "off";
        searchInput.required = true;
        searchInput.setAttribute("role", "combobox");
        searchInput.setAttribute("aria-autocomplete", "list");
        searchInput.setAttribute("aria-haspopup", "listbox");
        searchInput.setAttribute("aria-controls", `${dogSelect.id}-options`);
        searchInput.setAttribute("aria-expanded", "false");
        searchInput.setAttribute("aria-label", "Buscar perro o responsable");

        listbox.id = `${dogSelect.id}-options`;
        listbox.className = "appointment-dog-search__options";
        listbox.setAttribute("role", "listbox");
        listbox.hidden = true;

        wrapper.append(searchInput, listbox);
        dogSelect.before(wrapper);
        dogSelect.hidden = true;
        dogSelect.required = false;
        dogSelect.setAttribute("aria-hidden", "true");
        if (label) {
            label.htmlFor = searchInput.id;
        }

        const dogOptions = [...dogSelect.options].filter((option) => option.value);
        let activeIndex = -1;

        function closeOptions() {
            listbox.hidden = true;
            searchInput.setAttribute("aria-expanded", "false");
            searchInput.removeAttribute("aria-activedescendant");
            activeIndex = -1;
        }

        function chooseOption(option) {
            dogSelect.value = option.value;
            searchInput.value = option.textContent.trim();
            dogSelect.dispatchEvent(new Event("change", { bubbles: true }));
            closeOptions();
        }

        function renderOptions() {
            const query = normalize(searchInput.value);
            const matches = dogOptions.filter((option) =>
                normalize(option.textContent).includes(query),
            );
            listbox.replaceChildren();
            activeIndex = -1;
            searchInput.removeAttribute("aria-activedescendant");

            if (!matches.length) {
                const emptyMessage = document.createElement("p");
                emptyMessage.className = "appointment-dog-search__empty";
                emptyMessage.textContent = "No se encontraron perros o responsables.";
                listbox.append(emptyMessage);
            } else {
                matches.forEach((option, index) => {
                    const result = document.createElement("button");
                    result.type = "button";
                    result.id = `${dogSelect.id}-option-${index}`;
                    result.className = "appointment-dog-search__option";
                    result.setAttribute("role", "option");
                    result.dataset.value = option.value;
                    result.setAttribute(
                        "aria-selected",
                        option.value === dogSelect.value ? "true" : "false",
                    );
                    result.textContent = option.textContent.trim();
                    result.addEventListener("click", () => chooseOption(option));
                    listbox.append(result);
                });
            }

            listbox.hidden = false;
            searchInput.setAttribute("aria-expanded", "true");
        }

        function setActiveOption(nextIndex) {
            const options = [...listbox.querySelectorAll('[role="option"]')];
            if (!options.length) {
                return;
            }

            activeIndex = (nextIndex + options.length) % options.length;
            options.forEach((option, index) => {
                option.classList.toggle("is-active", index === activeIndex);
            });
            searchInput.setAttribute("aria-activedescendant", options[activeIndex].id);
            options[activeIndex].scrollIntoView({ block: "nearest" });
        }

        const initiallySelectedOption = dogOptions.find((option) => option.hasAttribute("selected"));
        dogSelect.value = initiallySelectedOption?.value || "";
        searchInput.value = initiallySelectedOption?.textContent.trim() || "";
        searchInput.addEventListener("focus", renderOptions);
        searchInput.addEventListener("input", () => {
            dogSelect.value = "";
            renderOptions();
        });
        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" && !listbox.hidden) {
                event.preventDefault();
                setActiveOption(activeIndex + 1);
            } else if (event.key === "ArrowUp" && !listbox.hidden) {
                event.preventDefault();
                setActiveOption(activeIndex - 1);
            } else if (event.key === "Enter" && activeIndex >= 0 && !listbox.hidden) {
                event.preventDefault();
                const activeOption = listbox.querySelectorAll('[role="option"]')[activeIndex];
                const selectedOption = dogOptions.find(
                    (option) => option.value === activeOption.dataset.value,
                );
                if (selectedOption) {
                    chooseOption(selectedOption);
                }
            } else if (event.key === "Escape") {
                closeOptions();
            }
        });
        document.addEventListener("pointerdown", (event) => {
            if (!wrapper.contains(event.target)) {
                closeOptions();
            }
        });

        return {
            setSelected(value) {
                dogSelect.value = value;
                searchInput.value = dogSelect.selectedOptions[0]?.textContent.trim() || "";
            },
        };
    }

    function normalize(value) {
        return value
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("es")
            .trim();
    }

    function updateAppointmentFilter(calendar) {
        if (!filterInput || !filterCount) {
            return;
        }

        const query = normalize(filterInput.value);
        let visibleCount = 0;
        calendar.getEvents().forEach((event) => {
            const props = event.extendedProps;
            const owners = props.owners.map((owner) => owner.name).join(" ");
            const searchableText = normalize(
                `${props.service} ${props.dog} ${owners} ${props.statusLabel}`,
            );
            const matches = searchableText.includes(query);
            event.setProp("display", matches ? "auto" : "none");
            if (matches) {
                visibleCount += 1;
            }
        });

        filterCount.textContent = `${visibleCount} ${visibleCount === 1 ? "cita" : "citas"}`;
    }

    if (filterInput && filterOptions) {
        const suggestions = new Set();
        events.forEach(({ extendedProps }) => {
            [
                extendedProps.service,
                extendedProps.dog,
                ...extendedProps.owners.map((owner) => owner.name),
            ].forEach((suggestion) => {
                if (suggestion) {
                    suggestions.add(suggestion);
                }
            });
        });
        [...suggestions].sort((a, b) => a.localeCompare(b, "es")).forEach((suggestion) => {
            const option = document.createElement("option");
            option.value = suggestion;
            filterOptions.append(option);
        });
    }

    function showCreateAppointment(dateStr) {
        if (!(createDialog instanceof HTMLDialogElement) || !appointmentForm || !dateInput) {
            return;
        }

        appointmentForm.reset();
        appointmentIdInput.value = "";
        originalStatusInput.value = "PENDING";
        discountsInput.value = "[]";
        paymentMethodInput.value = "";
        paymentMethodChoice.value = "";
        createDialog.dataset.appointmentId = "";
        createDialog.dataset.taxRate = "21.00";
        dogSearch?.setSelected("");
        statusInput.value = "PENDING";
        lastNonCompletedStatus = "PENDING";
        setEditMode(false);
        dateInput.value = dateStr.slice(0, 16);
        updateCreateDateLabel();
        createDialog.showModal();
    }

    function setEditMode(isEditing) {
        statusField.hidden = !isEditing;
        appointmentTitle.textContent = isEditing ? "Editar cita" : "Nueva cita";
        saveAppointmentButton.textContent = isEditing ? "Guardar cambios" : "Crear cita";
    }

    function updateCreateDateLabel() {
        if (!dateInput?.value) {
            document.getElementById("appointment-create-dialog-datetime").textContent = "";
            return;
        }
        const selectedDate = new Date(dateInput.value);
        document.getElementById("appointment-create-dialog-datetime").textContent =
            `${dateFormatter.format(selectedDate)} · ${timeFormatter.format(selectedDate)}`;
    }

    function showEditAppointment(event) {
        if (!(createDialog instanceof HTMLDialogElement) || !appointmentForm) {
            return;
        }

        const props = event.extendedProps;
        appointmentForm.reset();
        appointmentIdInput.value = event.id;
        createDialog.dataset.appointmentId = event.id;
        createDialog.dataset.taxRate = props.taxRate;
        dogSearch?.setSelected(String(props.dogId));
        appointmentForm.elements.namedItem("service_type").value = props.serviceType;
        dateInput.value = props.dateInput;
        priceInput.value = props.priceValue;
        appointmentForm.elements.namedItem("notes").value = props.notes;
        statusInput.value = props.status;
        paymentMethodInput.value = props.paymentMethod || "";
        paymentMethodChoice.value = props.paymentMethod || "";
        discountsInput.value = JSON.stringify(props.discounts || []);
        originalStatusInput.value = props.status;
        lastNonCompletedStatus = props.status === "COMPLETED" ? "PENDING" : props.status;
        previousStatus = lastNonCompletedStatus;
        completionConfirmed = false;
        setEditMode(true);
        updateCreateDateLabel();
        if (dialog.open) {
            dialog.close();
        }
        createDialog.showModal();
    }

    function formatCurrency(cents) {
        return new Intl.NumberFormat("es-ES", {
            style: "currency",
            currency: "EUR",
        }).format(cents / 100);
    }

    function createDiscountRow(discount = {}) {
        const row = document.createElement("div");
        row.className = "appointment-discount-row";
        const header = document.createElement("div");
        header.className = "appointment-discount-row__header";
        const title = document.createElement("strong");
        title.className = "appointment-discount-row__title";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "appointment-discount-row__remove";
        remove.textContent = "×";
        remove.setAttribute("aria-label", "Eliminar descuento");
        remove.addEventListener("click", () => {
            row.remove();
            updateDiscountRowLabels();
            updatePricePreview();
        });
        header.append(title, remove);

        const fields = document.createElement("div");
        fields.className = "appointment-discount-row__fields";
        const typeField = document.createElement("label");
        typeField.className = "appointment-discount-row__field";
        const typeLabel = document.createElement("span");
        typeLabel.textContent = "Tipo";
        const type = document.createElement("select");
        type.className = "appointment-discount-row__control";
        [
            ["PERCENTAGE", "Porcentaje (%)"],
            ["FIXED", "Importe fijo (€)"],
        ].forEach(([value, label]) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            type.append(option);
        });
        type.value = discount.type || "PERCENTAGE";
        typeField.append(typeLabel, type);

        const amountField = document.createElement("label");
        amountField.className = "appointment-discount-row__field";
        const amountLabel = document.createElement("span");
        const amount = document.createElement("input");
        amount.type = "number";
        amount.className = "appointment-discount-row__control";
        amount.min = "0";
        amount.step = "0.01";
        amount.required = true;
        amount.value = discount.value ?? "";
        amountField.append(amountLabel, amount);

        const descriptionField = document.createElement("label");
        descriptionField.className = "appointment-discount-row__field appointment-discount-row__field--description";
        const descriptionLabel = document.createElement("span");
        descriptionLabel.textContent = "Motivo del descuento";
        const description = document.createElement("input");
        description.type = "text";
        description.className = "appointment-discount-row__control appointment-discount-row__description";
        description.maxLength = 200;
        description.value = discount.description ?? "";
        description.placeholder = "Motivo del descuento";
        descriptionField.append(descriptionLabel, description);

        function updateAmountLabel() {
            amountLabel.textContent = type.value === "PERCENTAGE"
                ? "Porcentaje (%)"
                : "Importe (€)";
        }
        type.addEventListener("change", () => {
            updateAmountLabel();
            updatePricePreview();
        });
        amount.addEventListener("input", updatePricePreview);
        updateAmountLabel();
        fields.append(typeField, amountField, descriptionField);
        row.append(header, fields);
        discountRows.append(row);
        updateDiscountRowLabels();
    }

    function updateDiscountRowLabels() {
        discountRows.querySelectorAll(".appointment-discount-row__title").forEach((title, index) => {
            title.textContent = `Descuento ${index + 1}`;
        });
    }

    function currentDiscounts() {
        return [...discountRows.querySelectorAll(".appointment-discount-row")].map((row) => ({
            type: row.querySelector("select").value,
            value: row.querySelector("input").value,
            description: row.querySelector(".appointment-discount-row__description").value,
        }));
    }

    function updatePricePreview() {
        const gross = Number(priceInput.value || 0);
        const taxRate = Number(createDialog.dataset.taxRate || 21);
        const grossCents = Math.round(gross * 100);
        const baseCents = Math.round(grossCents / (1 + taxRate / 100));
        const taxCents = grossCents - baseCents;
        let remainingCents = baseCents;
        let errorMessage = "";

        for (const discount of currentDiscounts()) {
            if (discount.value === "" || !Number.isFinite(Number(discount.value))) {
                errorMessage = "Completa el importe de cada descuento o elimínalo.";
                break;
            }
            const value = Number(discount.value);
            if (value < 0 || (discount.type === "PERCENTAGE" && value > 100)) {
                errorMessage = "El descuento debe ser positivo y el porcentaje no puede superar el 100 %.";
                break;
            }
            const amountCents = discount.type === "PERCENTAGE"
                ? Math.round(remainingCents * value / 100)
                : Math.round(value * 100);
            if (amountCents > remainingCents) {
                errorMessage = "Los descuentos no pueden superar la base imponible restante.";
                break;
            }
            remainingCents -= amountCents;
        }

        const discountCents = baseCents - remainingCents;
        document.getElementById("completion-gross").textContent = formatCurrency(grossCents);
        document.getElementById("completion-base").textContent = formatCurrency(baseCents);
        document.getElementById("completion-tax").textContent = formatCurrency(taxCents);
        document.getElementById("completion-discount").textContent = `−${formatCurrency(discountCents)}`;
        document.getElementById("completion-total").textContent =
            formatCurrency(remainingCents + taxCents);
        const error = document.getElementById("completion-pricing-error");
        error.textContent = errorMessage;
        error.hidden = !errorMessage;
        document.getElementById("confirm-appointment-completion").disabled = Boolean(errorMessage);
    }

    function openCompletionDialog() {
        if (!(completionDialog instanceof HTMLDialogElement)) {
            return;
        }

        discountRows.replaceChildren();
        paymentMethodChoice.value = paymentMethodInput.value || "";
        try {
            const discounts = JSON.parse(discountsInput.value || "[]");
            discounts.forEach(createDiscountRow);
        } catch (error) {
            console.error("No se pudieron leer los descuentos guardados de la cita.", error);
        }
        updatePricePreview();
        completionDialog.showModal();
    }

    function setText(selector, value) {
        document.querySelector(selector).textContent = value;
    }

    function showAppointment(event) {
        selectedEvent = event;
        const details = event.extendedProps;
        const start = event.start;
        const end = event.end;
        const timeText = end
            ? `${timeFormatter.format(start)} - ${timeFormatter.format(end)}`
            : timeFormatter.format(start);
        const ownersList = document.getElementById("appointment-detail-owners");
        const notesRow = document.getElementById("appointment-detail-notes-row");

        setText("#appointment-detail-status", details.statusLabel);
        setText("#appointment-dialog-title", `${details.service} · ${details.dog}`);
        setText("#appointment-detail-datetime", `${dateFormatter.format(start)} · ${timeText}`);
        setText("#appointment-detail-service", details.service);
        setText("#appointment-detail-dog", details.dogLabel);
        setText("#appointment-detail-price", details.price);
        setText("#appointment-detail-notes", details.notes || "Sin notas");
        ownersList.replaceChildren();

        if (details.owners.length) {
            details.owners.forEach((owner) => {
                const item = document.createElement("li");
                const ownerDetails = document.createElement("span");
                ownerDetails.textContent = `${owner.name} · ${owner.phone}`;
                item.append(ownerDetails);
                if (owner.descartable) {
                    const warning = document.createElement("span");
                    warning.className = "discardable-badge";
                    warning.title = "Cliente marcado como no prioritario para futuras visitas";
                    warning.textContent = "No priorizar";
                    item.append(warning);
                }
                ownersList.append(item);
            });
        } else {
            const item = document.createElement("li");
            item.textContent = "Sin responsable activo asociado";
            ownersList.append(item);
        }

        notesRow.hidden = !details.notes;
        quickStatusAppointmentId.value = event.id;
        quickStatusForm.querySelectorAll("[data-quick-status]").forEach((button) => {
            button.hidden = button.dataset.quickStatus === details.status;
        });
        dialog.showModal();
    }

    const calendar = new window.FullCalendar.Calendar(calendarElement, {
        locale: "es",
        timeZone: calendarTimezone || "local",
        firstDay: 1,
        initialView: mobileCalendarQuery.matches ? "timeGridDay" : "timeGridWeek",
        height: "auto",
        expandRows: true,
        nowIndicator: true,
        allDaySlot: false,
        slotDuration: "00:30:00",
        slotLabelInterval: "01:00",
        slotMinTime: "00:00:00",
        slotMaxTime: "24:00:00",
        scrollTime: "08:00:00",
        defaultTimedEventDuration: "01:30:00",
        forceEventDuration: true,
        eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: mobileCalendarQuery.matches
                ? "dayGridMonth,timeGridDay"
                : "dayGridMonth,timeGridWeek,timeGridDay",
        },
        buttonText: {
            today: "Hoy",
            month: "Mes",
            week: "Semana",
            day: "Día",
        },
        dayMaxEvents: true,
        noEventsContent: "No hay citas para este periodo.",
        dateClick(argument) {
            if (argument.allDay) {
                return;
            }
            showCreateAppointment(argument.dateStr);
        },
        events,
        eventContent(argument) {
            const props = argument.event.extendedProps;
            const content = document.createElement("div");
            content.className = "calendar-event-content";

            if (argument.timeText) {
                const time = document.createElement("span");
                time.className = "calendar-event__time";
                time.textContent = argument.timeText;
                content.append(time);
            }

            const task = document.createElement("strong");
            task.className = "calendar-event__task";
            task.textContent = props.service;
            content.append(task);

            const dog = document.createElement("span");
            dog.className = "calendar-event__dog";
            dog.textContent = props.dogLabel;
            content.append(dog);

            const owner = document.createElement("span");
            owner.className = "calendar-event__owner";
            owner.textContent = props.owners.map((item) => item.name).join(", ") || "Sin responsable";
            content.append(owner);

            return { domNodes: [content] };
        },
        eventDidMount(argument) {
            const props = argument.event.extendedProps;
            const owners = props.owners.map((item) => item.name).join(", ") || "Sin responsable";
            argument.el.title = `${props.service} · ${props.dog} · ${owners} · ${props.statusLabel}`;
        },
        eventClick(argument) {
            argument.jsEvent.preventDefault();
            showAppointment(argument.event);
        },
    });

    calendar.render();
    mobileCalendarQuery.addEventListener("change", (argument) => {
        calendar.setOption("headerToolbar", {
            left: "prev,next today",
            center: "title",
            right: argument.matches
                ? "dayGridMonth,timeGridDay"
                : "dayGridMonth,timeGridWeek,timeGridDay",
        });
        calendar.changeView(argument.matches ? "timeGridDay" : "timeGridWeek");
        calendar.updateSize();
    });
    dogSearch = setupDogSearch();
    setEditMode(Boolean(createDialog.dataset.appointmentId));
    if (dogSelect?.value) {
        dogSearch?.setSelected(dogSelect.value);
    }

    selectedAppointmentButton?.addEventListener("click", () => {
        if (selectedEvent) {
            showEditAppointment(selectedEvent);
        }
    });

    quickStatusForm?.querySelectorAll("[data-quick-status]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!selectedEvent) {
                return;
            }
            if (button.dataset.quickStatus === "COMPLETED") {
                showEditAppointment(selectedEvent);
                statusInput.value = "COMPLETED";
                statusInput.dispatchEvent(new Event("change", { bubbles: true }));
                return;
            }
            if (
                button.dataset.quickStatus === "CANCELLED"
                && !window.confirm("¿Quieres cancelar esta cita?")
            ) {
                return;
            }
            quickStatusInput.value = button.dataset.quickStatus;
            quickStatusForm.requestSubmit();
        });
    });

    statusInput?.addEventListener("change", () => {
        if (statusInput.value === "COMPLETED" && createDialog.dataset.appointmentId) {
            previousStatus = lastNonCompletedStatus;
            openCompletionDialog();
        } else if (statusInput.value !== "COMPLETED") {
            lastNonCompletedStatus = statusInput.value;
            originalStatusInput.value = statusInput.value;
        }
    });

    appointmentForm?.addEventListener("submit", (event) => {
        if (
            statusInput?.value === "COMPLETED"
            && createDialog.dataset.appointmentId
            && !completionConfirmed
        ) {
            event.preventDefault();
            previousStatus = lastNonCompletedStatus;
            if (!completionDialog.open) {
                openCompletionDialog();
            }
        }
    });

    document.getElementById("add-appointment-discount")?.addEventListener("click", () => {
        createDiscountRow();
        updatePricePreview();
    });
    document.getElementById("confirm-appointment-completion")?.addEventListener("click", () => {
        if (document.getElementById("confirm-appointment-completion").disabled) {
            return;
        }
        if (!paymentMethodChoice.value) {
            paymentMethodChoice.reportValidity();
            return;
        }
        paymentMethodInput.value = paymentMethodChoice.value;
        discountsInput.value = JSON.stringify(currentDiscounts());
        completionConfirmed = true;
        completionDialog.close();
        window.requestAnimationFrame(() => appointmentForm.requestSubmit());
    });
    document.getElementById("cancel-appointment-completion")?.addEventListener("click", () => {
        statusInput.value = previousStatus;
        lastNonCompletedStatus = previousStatus;
        originalStatusInput.value = previousStatus;
        completionConfirmed = false;
        completionDialog.close();
    });
    paymentMethodChoice?.addEventListener("change", () => {
        paymentMethodInput.value = paymentMethodChoice.value;
    });
    priceInput?.addEventListener("input", updatePricePreview);
    dateInput?.addEventListener("input", updateCreateDateLabel);

    if (filterInput) {
        filterInput.addEventListener("input", () => updateAppointmentFilter(calendar));
        clearFilterButton?.addEventListener("click", () => {
            filterInput.value = "";
            updateAppointmentFilter(calendar);
            filterInput.focus();
        });
        updateAppointmentFilter(calendar);
    }

    if (createDialog instanceof HTMLDialogElement) {
        createDialog.querySelector("[data-close-appointment-form]")?.addEventListener(
            "click",
            () => createDialog.close(),
        );
        if (createDialog.dataset.openOnLoad === "true") {
            createDialog.showModal();
        }
    }
});
