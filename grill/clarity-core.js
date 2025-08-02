// clarity-core.js
document.addEventListener("DOMContentLoaded", () => {
    const storedIndustry = localStorage.getItem("industry");
    if (storedIndustry) {
        const selects = document.querySelectorAll("select[name='industry']");
        selects.forEach(select => {
            select.value = storedIndustry;
            select.dispatchEvent(new Event("change"));
        });
    }

    const inputs = document.querySelectorAll("input, select");
    inputs.forEach(input => {
        const key = input.name;
        if (!key) return;
        const stored = localStorage.getItem(key);
        if (stored) {
            input.value = stored;
            input.classList.add("prefilled");
        }

        input.addEventListener("input", () => {
            localStorage.setItem(key, input.value);
            input.classList.remove("prefilled");
        });
    });
});