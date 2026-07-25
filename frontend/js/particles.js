/* ===========================================
   BACKGROUND PARTICLES
=========================================== */

const particleCanvas = document.getElementById("particles");
let drawParticles = null;

if (particleCanvas) {

    const ctx = particleCanvas.getContext("2d");

    function resizeCanvas() {

        particleCanvas.width = window.innerWidth;
        particleCanvas.height = window.innerHeight;

    }

    resizeCanvas();

    window.addEventListener("resize", resizeCanvas);

    const particles = [];

    const TOTAL = 45;

    for (let i = 0; i < TOTAL; i++) {

        particles.push({

            x: Math.random() * particleCanvas.width,

            y: Math.random() * particleCanvas.height,

            vx: (Math.random() - 0.5) * 0.2,
            vy: (Math.random() - 0.5) * 0.2,

            size: Math.random() * 2 + 1,

            alpha: Math.random()

        });

    }

    function draw() {

        ctx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);

        particles.forEach(p => {

            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = particleCanvas.width;
            if (p.x > particleCanvas.width) p.x = 0;

            if (p.y < 0) p.y = particleCanvas.height;
            if (p.y > particleCanvas.height) p.y = 0;

            ctx.beginPath();

            ctx.arc(

                p.x,

                p.y,

                p.size,

                0,

                Math.PI * 2

            );

            ctx.fillStyle = `rgba(185,139,255,${p.alpha})`;

            ctx.fill();

        });

        for (let i = 0; i < particles.length; i++) {

            for (let j = i + 1; j < particles.length; j++) {

                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;

                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 90) {

                    ctx.beginPath();

                    ctx.moveTo(

                        particles[i].x,

                        particles[i].y

                    );

                    ctx.lineTo(

                        particles[j].x,

                        particles[j].y

                    );

                    ctx.strokeStyle = `rgba(197,255,107,${1 - dist / 130})`;

                    ctx.lineWidth = 0.6;

                    ctx.stroke();

                }

            }

        }

        if (!document.hidden) {
        requestAnimationFrame(draw);
        }

    }

    drawParticles = draw;
    draw();

}

/* ===========================================
PARALLAX
=========================================== */

let mouseFrame = false;

window.addEventListener("mousemove", e => {

    if (mouseFrame) return;

    mouseFrame = true;

    requestAnimationFrame(() => {

        const x = (e.clientX / window.innerWidth - 0.5) * 18;
        const y = (e.clientY / window.innerHeight - 0.5) * 18;

        const grid = document.querySelector(".grid-layer");
        const noise = document.querySelector(".noise-layer");

        if (grid) {
            grid.style.transform = `translate(${x}px,${y}px)`;
        }

        if (noise) {
            noise.style.transform = `translate(${x * 0.5}px,${y * 0.5}px)`;
        }

        mouseFrame = false;

    });

});

/* ===========================================
FLOATING CARDS
=========================================== */

document.querySelectorAll(".floating-card").forEach((card, index) => {

    card.animate(

        [

            {

                transform: "translateY(0px)"

            },

            {

                transform: `translateY(${-12 - index * 6}px)`

            },

            {

                transform: "translateY(0px)"

            }

        ],

        {

            duration: 3500 + index * 800,

            iterations: Infinity,

            easing: "ease-in-out"

        }

    );

});
document.addEventListener("visibilitychange", () => {

    if (!document.hidden && drawParticles) {
        requestAnimationFrame(drawParticles);
    }

});

function initAutoScrollToContent() {

    if (document.body && document.body.dataset.disableAutoScroll === "true") {
        return;
    }

    if (window.location.hash || window.scrollY !== 0) {
        return;
    }

    const firstSection = document.querySelector("section");

    if (!firstSection) {
        return;
    }

    const targetY = firstSection.offsetTop;

    if (targetY <= 0) {
        return;
    }

    // Only auto-scroll when there is a meaningful dead zone before content.
    // This avoids clipping layouts where section offset is only navbar-height.
    const minimumDeadZone = Math.max(180, Math.round(window.innerHeight * 0.35));

    if (targetY < minimumDeadZone) {
        return;
    }

    window.setTimeout(() => {

        window.scrollTo({
            top: targetY,
            behavior: "smooth"
        });

    }, 120);

}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAutoScrollToContent);
}
else {
    initAutoScrollToContent();
}