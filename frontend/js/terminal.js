/* ===========================================
   TERMINAL TYPEWRITER & AUTO-SCROLL
=========================================== */

const terminal = document.getElementById("terminal-output");

let terminalLines = [
    "> Booting Prereq Sleuth AI Engine...",
    "> Connecting to Graph Database...",
    "> Initializing Gemini Embedding Cache...",
    "> Diagnostic Engine: READY",
    "> Awaiting User Input_"
];

(async function fetchDynamicBootLog() {
    try {
        const apiBase = (typeof API_BASE !== 'undefined') ? API_BASE.replace('/api', '') : 'http://localhost:8000';
        const res = await fetch(apiBase + '/health');
        if (res.ok) {
            const data = await res.json();
            terminalLines = [
                `> Booting Prereq Sleuth Engine v0.3.0...`,
                `> Loaded ${data.subjects} subject graphs (${data.total_nodes} nodes, ${data.total_edges} edges)`,
                `> Gemini Embeddings: ${data.embeddings_ready === 'True' ? 'ONLINE (gemini-embedding-2)' : 'BUILDING'}`,
                `> Diagnostic Engine Status: ${data.status.toUpperCase()}`,
                `> Awaiting Concept Scan Query_`
            ];
        }
    } catch (e) {
        terminalLines.push("> System Warning: Backend offline - local cache fallback active");
    }
})();


let lineIndex = 0;
let charIndex = 0;

function autoScrollTerminal() {
    const termBody = document.querySelector(".terminal-body");
    if (termBody) {
        termBody.scrollTop = termBody.scrollHeight;
    }
}

if (terminal) {
    const observer = new MutationObserver(() => {
        autoScrollTerminal();
    });
    observer.observe(terminal, { childList: true, characterData: true, subtree: true });
}


function typeTerminal(){
    if(!terminal) return;

    if(lineIndex >= terminalLines.length){
        setTimeout(()=>{
            terminal.innerHTML="█";
            lineIndex=0;
            charIndex=0;
            typeTerminal();
        }, 3000);
        return;
    }

    const line = terminalLines[lineIndex];

    if(charIndex < line.length){
        terminal.innerHTML =
            terminal.innerHTML.replace("█","") +
            line.charAt(charIndex) +
            "█";
        charIndex++;
        autoScrollTerminal();
        setTimeout(typeTerminal, 35);
    } else {
        terminal.innerHTML =
            terminal.innerHTML.replace("█","") +
            "<br>█";
        lineIndex++;
        charIndex=0;
        autoScrollTerminal();
        setTimeout(typeTerminal, 220);
    }
}

window.addEventListener("load", typeTerminal);


/* ===========================================
LIVE SYSTEM STATUS (from /health API)
=========================================== */

let liveStatusMessages = [
    "Checking prerequisites...",
    "Scanning dependency tree...",
    "Building concept graph...",
    "Locating weak node...",
    "Generating recovery path...",
    "System ready"
];

(async function loadRealStatus() {
    try {
        const API = (typeof API_BASE !== 'undefined') ? API_BASE.replace('/api', '') : 'http://localhost:8000';
        const res = await fetch(API + '/health');
        if (res.ok) {
            const data = await res.json();
            liveStatusMessages = [
                `> ${data.subjects || '?'} subjects loaded`,
                `> ${data.total_nodes || data.nodes || '?'} concept nodes online`,
                `> ${data.total_edges || '?'} dependency links mapped`,
                `> Embeddings: ${data.embeddings_ready === 'True' ? 'READY' : 'building...'}`,
                `> Engine status: ${data.status || 'unknown'}`,
                `> AI Diagnostic Engine: OPERATIONAL`
            ];
        }
    } catch (e) {
        // Fallback
    }
})();

setInterval(()=>{
    if(!terminal) return;

    const random = liveStatusMessages[
        Math.floor(Math.random() * liveStatusMessages.length)
    ];

    const status=document.createElement("div");
    status.className = "stream-line text-sm font-mono text-muted py-1";
    status.innerHTML = random.startsWith(">") ? random : "> " + random;

    terminal.appendChild(status);

    if(terminal.children.length > 20){
        terminal.removeChild(terminal.firstChild);
    }
    autoScrollTerminal();
}, 4500);