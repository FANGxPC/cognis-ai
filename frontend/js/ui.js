// ======================================================
// Shared UI Engine
// ======================================================

const ProgressStages = [
    "SCAN",
    "QUIZ",
    "ROOT",
    "LESSON",
    "PRACTICE",
    "VERIFY"
];

// ------------------------------------------------------
// Toast
// ------------------------------------------------------

function showToast(message, type = "success") {

    let toast = document.getElementById("globalToast");

    if (!toast) {

        toast = document.createElement("div");

        toast.id = "globalToast";

        toast.className = "toast";

        document.body.appendChild(toast);

    }

    toast.className = `toast ${type}`;

    toast.innerHTML = message;

    toast.classList.add("visible");

    clearTimeout(toast.timer);

    toast.timer = setTimeout(() => {

        toast.classList.remove("visible");

    }, 3000);

}

// ------------------------------------------------------
// Loading Overlay
// ------------------------------------------------------

function showLoader(title = "Processing...", message = "") {

    let overlay = document.getElementById("loadingOverlay");

    if (!overlay) {

        overlay = document.createElement("div");

        overlay.id = "loadingOverlay";

        overlay.innerHTML = `

<div class="loader-window">

<h2 id="loaderTitle"></h2>

<p id="loaderMessage"></p>

<div class="loader-bar">

<div class="loader-progress"></div>

</div>

</div>

`;

        document.body.appendChild(overlay);

    }

    document.getElementById("loaderTitle").textContent = title;

    document.getElementById("loaderMessage").textContent = message;

    overlay.classList.add("active");

}

function hideLoader() {

    const overlay = document.getElementById("loadingOverlay");

    if (overlay) {

        overlay.classList.remove("active");

    }

}

// ------------------------------------------------------
// Error Card
// ------------------------------------------------------

function showError(container, title, message) {

    container.innerHTML = `

<div class="feature-card">

<h2>${title}</h2>

<p class="mt-5">${message}</p>

</div>

`;

}

// ------------------------------------------------------
// Storage Helpers
// ------------------------------------------------------

const Storage = {

    get(key, fallback = null) {

        try {

            return JSON.parse(localStorage.getItem(key));

        }

        catch {

            return localStorage.getItem(key) ?? fallback;

        }

    },

    set(key, value) {

        if (typeof value === "object") {

            localStorage.setItem(

                key,

                JSON.stringify(value)

            );

        }

        else {

            localStorage.setItem(

                key,

                value

            );

        }

    }

};
// ======================================================
// Workflow Progress
// ======================================================

const WorkflowStages = [

"SCAN",

"QUIZ",

"ROOT",

"LESSON",

"PRACTICE",

"VERIFY"

];

function renderWorkflow(currentStage){

const existing=document.getElementById("workflowProgress");

if(existing){

existing.remove();

}

const wrapper=document.createElement("div");

wrapper.id="workflowProgress";

wrapper.className="workflow-progress";

WorkflowStages.forEach((stage,index)=>{

const item=document.createElement("div");

item.className="workflow-step";

const currentIndex=

WorkflowStages.indexOf(currentStage);

if(index<currentIndex){

item.classList.add("completed");

}

else if(index===currentIndex){

item.classList.add("active");

}

item.innerHTML=`

<div class="workflow-circle">

${index<currentIndex?"✓":index+1}

</div>

<div class="workflow-label">

${stage}

</div>

`;

wrapper.appendChild(item);

if(index!==WorkflowStages.length-1){

const line=document.createElement("div");

line.className="workflow-line";

wrapper.appendChild(line);

}

});

return wrapper;

}