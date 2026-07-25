/* ===========================================
   CUSTOM CURSOR
=========================================== */

const dot=document.getElementById("cursor-dot");
const ring=document.getElementById("cursor-ring");
if (!dot || !ring) {
    throw new Error("Custom cursor elements not found.");
}
let mouseX=window.innerWidth/2;
let mouseY=window.innerHeight/2;

let ringX=mouseX;
let ringY=mouseY;

window.addEventListener("mousemove",(e)=>{

    mouseX=e.clientX;
    mouseY=e.clientY;

    dot.style.left=mouseX+"px";
    dot.style.top=mouseY+"px";

});

function animateCursor(){

    ringX+=(mouseX-ringX)*0.45;
    ringY+=(mouseY-ringY)*0.45;

    ring.style.left=ringX+"px";
    ring.style.top=ringY+"px";

    requestAnimationFrame(animateCursor);

}

animateCursor();

/* ===========================================
HOVER EFFECT
=========================================== */

const hoverTargets = document.querySelectorAll(
    "a, button, .feature-card, .timeline-card, .stat-card"
);

hoverTargets.forEach(item=>{

    item.addEventListener("mouseenter",()=>{

        ring.style.width="70px";
        ring.style.height="70px";
        ring.style.borderColor="#C5FF6B";
        ring.style.background="rgba(197,255,107,.08)";

    });

    item.addEventListener("mouseleave",()=>{

        ring.style.width="42px";
        ring.style.height="42px";
        ring.style.borderColor="rgba(197,255,107,.45)";
        ring.style.background="transparent";

    });

});

/* ===========================================
CLICK EFFECT
=========================================== */

window.addEventListener("mousedown",()=>{

    dot.style.transform="translate(-50%,-50%) scale(.55)";
    ring.style.transform="translate(-50%,-50%) scale(.75)";

});

window.addEventListener("mouseup",()=>{

    dot.style.transform="translate(-50%,-50%) scale(1)";
    ring.style.transform="translate(-50%,-50%) scale(1)";

});

/* ===========================================
CURSOR HIDE
=========================================== */

document.addEventListener("mouseleave",()=>{

    dot.style.opacity="0";
    ring.style.opacity="0";

});

document.addEventListener("mouseenter",()=>{

    dot.style.opacity="1";
    ring.style.opacity="1";

});