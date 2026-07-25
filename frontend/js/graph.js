/* ===========================================
   KNOWLEDGE GRAPH
=========================================== */

const graphContainer = document.getElementById("graph-preview");

if(graphContainer){

    const canvas = document.createElement("canvas");

    canvas.width = graphContainer.clientWidth;
    canvas.height = graphContainer.clientHeight;

    graphContainer.appendChild(canvas);

    const ctx = canvas.getContext("2d");

    let nodes = [];

    const NODE_COUNT = 28;

    for(let i=0;i<NODE_COUNT;i++){

        nodes.push({

            x:Math.random()*canvas.width,

            y:Math.random()*canvas.height,

            vx:(Math.random()-.5)*0.35,

            vy:(Math.random()-.5)*0.35,

            r:Math.random()*3+3,

            pulse:Math.random()*Math.PI*2

        });

    }

    function resize(){

        canvas.width=graphContainer.clientWidth;
        canvas.height=graphContainer.clientHeight;

    }

    window.addEventListener("resize",resize);

    function drawConnections(){

        for(let i=0;i<nodes.length;i++){

            for(let j=i+1;j<nodes.length;j++){

                const dx=nodes[i].x-nodes[j].x;
                const dy=nodes[i].y-nodes[j].y;

                const dist=Math.sqrt(dx*dx+dy*dy);

                if(dist<170){

                    ctx.strokeStyle=`rgba(185,139,255,${1-dist/170})`;

                    ctx.lineWidth=1;

                    ctx.beginPath();

                    ctx.moveTo(nodes[i].x,nodes[i].y);

                    ctx.lineTo(nodes[j].x,nodes[j].y);

                    ctx.stroke();

                }

            }

        }

    }

    function drawNodes(){

        nodes.forEach(node=>{

            node.x+=node.vx;
            node.y+=node.vy;

            if(node.x<0||node.x>canvas.width) node.vx*=-1;
            if(node.y<0||node.y>canvas.height) node.vy*=-1;

            node.pulse+=0.05;

            const radius=node.r+Math.sin(node.pulse)*0.8;

            ctx.beginPath();

            ctx.arc(node.x,node.y,radius,0,Math.PI*2);

            ctx.fillStyle="#C5FF6B";

            ctx.shadowBlur=15;

            ctx.shadowColor="#C5FF6B";

            ctx.fill();

            ctx.shadowBlur=0;

        });

    }

    function animate(){

        ctx.clearRect(0,0,canvas.width,canvas.height);

        drawConnections();

        drawNodes();

        requestAnimationFrame(animate);

    }

    animate();

}

/* ===========================================
RANDOM NODE FLASH
=========================================== */

setInterval(()=>{

    if(!graphContainer) return;

    graphContainer.animate([

        {

            filter:"brightness(1)"

        },

        {

            filter:"brightness(1.25)"

        },

        {

            filter:"brightness(1)"

        }

    ],{

        duration:350

    });

},2200);