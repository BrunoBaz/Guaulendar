document.addEventListener("DOMContentLoaded", () => {
    const normalize = (value) => value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase("es")
        .trim();

    document.querySelectorAll("[data-breed-combobox]").forEach((combobox) => {
        const input = combobox.querySelector("[data-breed-input]");
        const list = combobox.querySelector(".breed-combobox__options");

        if (!input || !list) {
            return;
        }

        const options = [...list.querySelectorAll("[data-breed-option]")];

        const closeList = () => {
            list.hidden = true;
            input.setAttribute("aria-expanded", "false");
        };

        const filterOptions = () => {
            const query = normalize(input.value);
            let visibleCount = 0;

            options.forEach((option) => {
                const matches = !query || normalize(option.dataset.breedValue).includes(query);
                option.hidden = !matches;
                if (matches) {
                    visibleCount += 1;
                }
            });

            list.hidden = visibleCount === 0;
            input.setAttribute("aria-expanded", visibleCount > 0 ? "true" : "false");
        };

        input.addEventListener("focus", filterOptions);
        input.addEventListener("input", filterOptions);
        input.addEventListener("blur", closeList);
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeList();
            }
        });

        list.addEventListener("mousedown", (event) => event.preventDefault());
        options.forEach((option) => {
            option.addEventListener("click", () => {
                input.value = option.dataset.breedValue;
                closeList();
            });
        });
    });
});
