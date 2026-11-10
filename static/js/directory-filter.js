document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-directory-filter]").forEach((input) => {
        const grid = document.getElementById(input.dataset.directoryFilter);
        const count = document.getElementById(input.dataset.directoryCount);
        const emptyState = document.querySelector(
            `[data-filter-empty="${input.dataset.directoryFilter}"]`,
        );
        const items = grid ? [...grid.querySelectorAll("[data-filter-item]")] : [];
        const statusFilter = document.querySelector(
            `[data-filter-status-for="${input.dataset.directoryFilter}"]`,
        );

        if (!grid || !count) {
            return;
        }

        const normalize = (value) => value
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("es")
            .trim();

        const updateResults = () => {
            const query = normalize(input.value);
            const status = statusFilter?.value || "all";
            let visibleCount = 0;

            items.forEach((item) => {
                const matches = normalize(item.textContent).includes(query)
                    && (status === "all" || item.dataset.status === status);
                item.hidden = !matches;
                if (matches) {
                    visibleCount += 1;
                }
            });

            const label = visibleCount === 1
                ? input.dataset.singularLabel
                : input.dataset.pluralLabel;
            count.textContent = `${visibleCount} ${label}`;

            if (emptyState) {
                emptyState.hidden = visibleCount > 0 || (!query && status === "all");
            }
        };

        input.addEventListener("input", updateResults);
        statusFilter?.addEventListener("change", updateResults);
        input.form?.addEventListener("reset", () => requestAnimationFrame(updateResults));

        document.querySelector(`[data-clear-filter="${input.id}"]`)?.addEventListener("click", () => {
            input.value = "";
            updateResults();
            input.focus();
        });
    });
});
