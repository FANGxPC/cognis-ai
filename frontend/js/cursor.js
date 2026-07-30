/* ===========================================
   CUSTOM CURSOR (FLICKER-FREE & STABLE)
=========================================== */

const dot = document.getElementById("cursor-dot");
const ring = document.getElementById("cursor-ring");

if (dot && ring) {
    // Strictly disable pointer events to prevent mouse interference/flicker
    dot.style.pointerEvents = "none";
    ring.style.pointerEvents = "none";

    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let ringX = mouseX;
    let ringY = mouseY;

    window.addEventListener("mousemove", (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        dot.style.left = mouseX + "px";
        dot.style.top = mouseY + "px";
    }, { passive: true });

    function animateCursor() {
        ringX += (mouseX - ringX) * 0.35;
        ringY += (mouseY - ringY) * 0.35;
        ring.style.left = ringX + "px";
        ring.style.top = ringY + "px";
        requestAnimationFrame(animateCursor);
    }
    animateCursor();

    // Event Delegation for hover effects to prevent thrashing
    document.addEventListener("mouseover", (e) => {
        if (e.target && e.target.closest && e.target.closest("a, button, .feature-card, .timeline-card, .stat-card")) {
            ring.style.width = "54px";
            ring.style.height = "54px";
            ring.style.borderColor = "#C5FF6B";
            ring.style.background = "rgba(197,255,107,.08)";
        }
    }, { passive: true });

    document.addEventListener("mouseout", (e) => {
        if (e.target && e.target.closest && e.target.closest("a, button, .feature-card, .timeline-card, .stat-card")) {
            ring.style.width = "38px";
            ring.style.height = "38px";
            ring.style.borderColor = "rgba(197,255,107,.45)";
            ring.style.background = "transparent";
        }
    }, { passive: true });

    window.addEventListener("mousedown", () => {
        dot.style.transform = "translate(-50%, -50%) scale(.55)";
        ring.style.transform = "translate(-50%, -50%) scale(.75)";
    });

    window.addEventListener("mouseup", () => {
        dot.style.transform = "translate(-50%, -50%) scale(1)";
        ring.style.transform = "translate(-50%, -50%) scale(1)";
    });

    document.addEventListener("mouseleave", () => {
        dot.style.opacity = "0";
        ring.style.opacity = "0";
    });

    document.addEventListener("mouseenter", () => {
        dot.style.opacity = "1";
        ring.style.opacity = "1";
    });
}