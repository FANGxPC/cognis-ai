/* ===========================================
   KNOWLEDGE GRAPH
=========================================== */

const graphContainer = document.getElementById("graph-preview");

if (graphContainer) {

    const canvas = document.createElement("canvas");


    graphContainer.appendChild(canvas);
    canvas.width = graphContainer.clientWidth;
    canvas.height = graphContainer.clientHeight;

    const ctx = canvas.getContext("2d");

    let nodes = [];
    let mouse = {
        x: -1000,
        y: -1000
    };

    canvas.addEventListener("mousemove", e => {

        const rect = canvas.getBoundingClientRect();

        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;

    });

    canvas.addEventListener("mouseleave", () => {

        mouse.x = -1000;
        mouse.y = -1000;

    });
    let clusters = [
        { name: "Linear Algebra", x: 0.35, y: 0.35, nodes: 10 },
        { name: "Data Structures", x: 0.65, y: 0.65, nodes: 12 }
    ];

    function buildNodesFromClusters() {
        nodes = [];
        clusters.forEach(cluster => {
            const cx = cluster.x * canvas.width;
            const cy = cluster.y * canvas.height;
            for (let i = 0; i < cluster.nodes; i++) {
                const angle = (Math.PI * 2 / cluster.nodes) * i;
                const radius = 40 + Math.random() * 60;
                nodes.push({
                    x: cx + Math.cos(angle) * radius,
                    y: cy + Math.sin(angle) * radius,
                    vx: (Math.random() - .5) * 0.25,
                    vy: (Math.random() - .5) * 0.25,
                    r: 3 + Math.random() * 2,
                    pulse: Math.random() * Math.PI * 2,
                    energy: 0,
                    active: false,
                    cluster: cluster.name,
                    type: i == 0 ? "root" : (i < 3 ? "major" : "minor")
                });
            }
        });
    }

    buildNodesFromClusters();

    // Fetch real subject data from backend API
    (async function syncClustersWithAPI() {
        try {
            const apiBase = (typeof API_BASE !== 'undefined') ? API_BASE : 'http://localhost:8000/api';
            const res = await fetch(apiBase + '/subjects');
            if (res.ok) {
                const data = await res.json();
                if (data.subjects && data.subjects.length > 0) {
                    const positions = [
                        { x: 0.28, y: 0.28 },
                        { x: 0.72, y: 0.28 },
                        { x: 0.50, y: 0.55 },
                        { x: 0.25, y: 0.78 },
                        { x: 0.75, y: 0.78 }
                    ];
                    clusters = data.subjects.map((sub, idx) => ({
                        name: sub.title,
                        x: positions[idx % positions.length].x,
                        y: positions[idx % positions.length].y,
                        nodes: Math.max(5, sub.node_count || 8)
                    }));
                    buildNodesFromClusters();

                }
            }
        } catch (e) {
            // Keep fallback clusters
        }
    })();


    function resize() {

        canvas.width = graphContainer.clientWidth;
        canvas.height = graphContainer.clientHeight;

    }
    resize();
    window.addEventListener("resize", resize);

    function drawConnections() {

        for (let i = 0; i < nodes.length; i++) {

            for (let j = i + 1; j < nodes.length; j++) {

                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;

                const dist = Math.sqrt(dx * dx + dy * dy);

                const sameCluster = nodes[i].cluster === nodes[j].cluster;
                const maxDist = sameCluster ? 220 : 120;

                if (dist < maxDist) {

                    const glow = (nodes[i].energy + nodes[j].energy) / 2;

                    const opacity = Math.max((1 - dist / maxDist) * 0.25, glow);

                    ctx.strokeStyle = sameCluster
                        ? `rgba(197,255,107,${opacity})`
                        : `rgba(167,139,250,${opacity * 0.6})`;

                    ctx.lineWidth = 1;

                    ctx.beginPath();

                    ctx.moveTo(nodes[i].x, nodes[i].y);

                    ctx.lineTo(nodes[j].x, nodes[j].y);

                    ctx.stroke();

                }

            }

        }

    }

    function drawNodes() {

        nodes.forEach(node => {

            // Movement
            if (node.type !== "root") {

                node.x += node.vx;
                node.y += node.vy;

            }
            const home = clusters.find(c => c.name === node.cluster);

            if (home) {
                const targetX = home.x * canvas.width;
                const targetY = home.y * canvas.height;

                if (node.type === "root") {

                    node.x += (targetX - node.x) * 0.08;
                    node.y += (targetY - node.y) * 0.08;

                }
                else {

                    node.vx += (targetX - node.x) * 0.0008;
                    node.vy += (targetY - node.y) * 0.0008;

                }
            }

            node.vx *= 0.985;
            node.vy *= 0.985;

            if (node.x < 0 || node.x > canvas.width) node.vx *= -1;
            if (node.y < 0 || node.y > canvas.height) node.vy *= -1;

            node.pulse += 0.05;
            const dx = node.x - mouse.x;
            const dy = node.y - mouse.y;

            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 90) {

                const force = (90 - dist) / 90;

                node.vx += (dx / dist) * force * 0.5;
                node.vy += (dy / dist) * force * 0.5;

            }

            // Radius
            let radius;

            switch (node.type) {

                case "root":
                    radius = 10;
                    break;

                case "major":
                    radius = 7;
                    break;

                default:
                    radius = 4;

            }

            const pulseRadius = radius + Math.sin(node.pulse) * 0.6;
            // Color
            if (node.type === "root") {
                ctx.fillStyle = "#D6B3FF";
            } else if (node.type === "major") {
                ctx.fillStyle = "#A78BFA";
            } else {
                ctx.fillStyle = "#8CF26A";
            }

            // Glow
            const hoverBoost = dist < 90 ? 15 : 0;

            ctx.shadowBlur =
                (node.active ? 35 : (node.type === "root" ? 25 : 12))
                + hoverBoost;
            ctx.shadowColor = ctx.fillStyle;

            // Draw node
            if (node.type === "root") {

                ctx.beginPath();

                ctx.arc(
                    node.x,
                    node.y,
                    pulseRadius + 8 + Math.sin(node.pulse) * 2,
                    0,
                    Math.PI * 2
                );

                ctx.strokeStyle = "rgba(214,179,255,0.25)";
                ctx.lineWidth = 2;
                ctx.stroke();

            }

            ctx.beginPath();
            ctx.arc(node.x, node.y, pulseRadius, 0, Math.PI * 2);
            ctx.fill();

            ctx.shadowBlur = 0;

            // Labels
            if (node.type === "root") {

                const lightTheme =
                    document.documentElement.dataset.theme === "light";

                ctx.fillStyle = lightTheme
                    ? "#2F2F37"
                    : "#FFFFFF";

                ctx.font = "600 16px JetBrains Mono";

                ctx.textAlign = "center";

                ctx.shadowColor = "rgba(0,0,0,.7)";
                ctx.shadowBlur = 8;

                let labelText = node.cluster || "";
                if (labelText.length > 18) {
                    labelText = labelText.slice(0, 15) + "...";
                }

                ctx.fillText(
                    labelText,
                    node.x,
                    node.y - 18
                );


                ctx.shadowBlur = 0;

            }

        });

    }
    function animate() {

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        nodes.forEach(node => {

            node.energy *= 0.96;

            if (node.energy < 0.05) {

                node.active = false;

            }

        });


        drawConnections();

        drawNodes();

        requestAnimationFrame(animate);

    }

    animate();
    setInterval(() => {

        const node = nodes[Math.floor(Math.random() * nodes.length)];

        node.active = true;

        node.energy = 1;

    }, 900);
}

/* ===========================================
RANDOM NODE FLASH
=========================================== */

setInterval(() => {

    if (!graphContainer) return;

    graphContainer.animate([

        {

            filter: "brightness(1)"

        },

        {

            filter: "brightness(1.25)"

        },

        {

            filter: "brightness(1)"

        }

    ], {

        duration: 350

    });

}, 2200);