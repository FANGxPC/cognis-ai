/* ===========================================
   MAIN
=========================================== */

document.addEventListener("DOMContentLoaded", () => {

    initCounters();

    initScrollReveal();

    initNavbar();

});

/* ===========================================
COUNTERS
=========================================== */

function initCounters() {

    const counters = document.querySelectorAll(".counter");

    const observer = new IntersectionObserver(entries => {

        entries.forEach(entry => {

            if (!entry.isIntersecting) return;

            const counter = entry.target;

            const target = +counter.dataset.target;

            let current = 0;

            const increment = Math.ceil(target / 100);

            const timer = setInterval(() => {

                current += increment;

                if (current >= target) {

                    current = target;

                    clearInterval(timer);

                }

                counter.textContent = current;

            }, 20);

            observer.unobserve(counter);

        });

    }, {

        threshold: .5

    });

    counters.forEach(counter => observer.observe(counter));

}

/* ===========================================
SCROLL REVEAL
=========================================== */

function initScrollReveal() {

    const items = document.querySelectorAll(

        ".feature-card,.timeline-step,.stat-card,.cta-panel"

    );

    const observer = new IntersectionObserver(entries => {

        entries.forEach(entry => {

            if (entry.isIntersecting) {

                entry.target.style.opacity = "1";

                entry.target.style.transform = "translateY(0)";

            }

        });

    }, {

        threshold: .15

    });

    items.forEach(item => {

        item.style.opacity = "0";

        item.style.transform = "translateY(60px)";

        item.style.transition = "all .8s ease";

        observer.observe(item);

    });

}

/* ===========================================
NAVBAR
=========================================== */

function initNavbar() {

    const navbar = document.querySelector("nav");

    window.addEventListener("scroll", () => {

        if (window.scrollY > 60) {

            navbar.classList.add(

                "backdrop-blur-xl",

                "bg-black/20",

                "shadow-2xl"

            );

        }

        else {

            navbar.classList.remove(

                "backdrop-blur-xl",

                "bg-black/20",

                "shadow-2xl"

            );

        }

    });

}

/* ===========================================
BUTTON RIPPLE
=========================================== */

document.querySelectorAll(

    ".primary-button,.secondary-button,.scan-button"

).forEach(button => {

    button.addEventListener("click", e => {

        const ripple = document.createElement("span");

        const size = Math.max(

            button.clientWidth,

            button.clientHeight

        );

        ripple.style.width = size + "px";

        ripple.style.height = size + "px";

        ripple.style.left = e.offsetX - size / 2 + "px";

        ripple.style.top = e.offsetY - size / 2 + "px";

        ripple.className = "ripple";

        button.appendChild(ripple);

        setTimeout(() => {

            ripple.remove();

        }, 600);

    });

});
const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) {
    logoutBtn.onclick = () => {
        sessionStorage.clear();
        localStorage.removeItem(STORAGE_KEYS.TOKEN);
        location.href = "pages/login.html";
    };
}
