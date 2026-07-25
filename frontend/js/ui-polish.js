/* ===========================================
   UI POLISH HELPERS
=========================================== */

document.addEventListener("DOMContentLoaded", () => {

    initCommandHotkey();
    initHotkeyHints();
    initTerminalStream();

});

function initCommandHotkey() {

    document.addEventListener("keydown", event => {

        if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") {
            return;
        }

        event.preventDefault();

        const preferred = document.querySelector("[data-command-focus]");
        const fallback = document.querySelector("input:not([type='hidden']), select, textarea, button");
        const target = preferred || fallback;

        if (target && typeof target.focus === "function") {
            target.focus();
            if (target.select && target.tagName === "INPUT") {
                target.select();
            }
        }

    });

}

function initHotkeyHints() {

    document.querySelectorAll("[data-hotkey-hint]").forEach(element => {

        const hint = document.createElement("span");
        hint.className = "quick-hint";
        hint.innerHTML = `Quick Focus <kbd>${element.dataset.hotkeyHint}</kbd>`;

        element.insertAdjacentElement("afterend", hint);

    });

}

function initTerminalStream() {

    const terminal = document.getElementById("terminal-output");

    if (!terminal) {
        return;
    }

    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    node.classList.add("stream-line");
                }
            });
        });
    });

    observer.observe(terminal, {
        childList: true
    });

}
