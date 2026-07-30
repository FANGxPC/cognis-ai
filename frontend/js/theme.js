const toggle = document.getElementById("themeToggle");

const currentTheme = localStorage.getItem("theme") || "dark";

document.documentElement.setAttribute("data-theme", currentTheme);

updateIcon(currentTheme);

if (toggle) {
    toggle.addEventListener("click", () => {
        const current =
            document.documentElement.getAttribute("data-theme");

        const next =
            current === "dark"
                ? "light"
                : "dark";

        document.documentElement.setAttribute("data-theme", next);

        localStorage.setItem("theme", next);

        updateIcon(next);
    });
}

function updateIcon(theme) {
    if (!toggle) return;

    toggle.textContent = theme === "dark" ? "☀️" : "🌙";

    toggle.setAttribute(
        "aria-label",
        theme === "dark"
            ? "Switch to light mode"
            : "Switch to dark mode"
    );
}