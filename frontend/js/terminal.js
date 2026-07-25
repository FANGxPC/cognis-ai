/* ===========================================
   TERMINAL TYPEWRITER
=========================================== */

const terminal = document.getElementById("terminal-output");

const terminalLines = [

"> Booting XRAY Engine...",
"",
"> Loading Knowledge Graph...",
"",
"> Connecting Dependency Database...",
"",
"> Mapping Concept Relationships...",
"",
"> AI Diagnostic Engine Online...",
"",
"> Awaiting User Input_"

];

let lineIndex = 0;
let charIndex = 0;

function typeTerminal(){

    if(!terminal) return;

    if(lineIndex >= terminalLines.length){

        setTimeout(()=>{

            terminal.innerHTML="█";;
            lineIndex=0;
            charIndex=0;
            typeTerminal();

        },3000);

        return;

    }

    const line = terminalLines[lineIndex];

    if(charIndex < line.length){

        terminal.innerHTML =
        terminal.innerHTML.replace("█","") +
        line.charAt(charIndex) +
"█";

        charIndex++;

        setTimeout(typeTerminal,35);

    }

    else{

        terminal.innerHTML =
        terminal.innerHTML.replace("█","") +
        "<br>█";

        lineIndex++;

        charIndex=0;

        setTimeout(typeTerminal,220);

    }

}

window.addEventListener("load",typeTerminal);



/* ===========================================
FAKE SYSTEM STATUS
=========================================== */

const statusMessages=[

"Checking prerequisites...",
"Scanning dependency tree...",
"Building concept graph...",
"Locating weak node...",
"Generating recovery path...",
"Confidence: 98.6%"

];

setInterval(()=>{

    if(!terminal) return;

    const random=statusMessages[
        Math.floor(Math.random()*statusMessages.length)
    ];

    const status=document.createElement("div");

    status.className = "stream-line text-muted text-2xl";
    status.innerHTML="> "+random;

    terminal.appendChild(status);

    if(terminal.children.length>12){

        terminal.removeChild(terminal.firstChild);

    }

},4500);