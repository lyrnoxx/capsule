const BACKGROUND = "#101010"
const FOREGROUND = "#50FF50"

console.log(game)

const menu = document.getElementById("ui-layer");
const sliderSpeed = document.getElementById("speed-slider");
const fg = document.getElementById("fg-picker");
const bg = document.getElementById("bg-picker");


function toggleMenu(){
    menu.classList.toggle("hidden")
}

window.addEventListener("keydown", (e)=> {
    if (e.key.toLocaleLowerCase() == "h") toggleMenu()
})

function resizeCanvas(){
    game.width = window.innerWidth
    game.height = window.innerHeight
}
resizeCanvas()

window.addEventListener('resize', resizeCanvas)
document.body.style.margin = "0"
document.body.style.overflow = "hidden"

const ctx = game.getContext("2d")
console.log(ctx)

function clear() {
    ctx.fillStyle = bg.value
    ctx.fillRect(0, 0, game.width, game.height)
}

function point({x, y}){
    const s = 20
    ctx.fillStyle = fg.value
    ctx.fillRect(x - s/2, y -s/2, s, s)
}

function line(p1, p2){
    ctx.lineWidth = 3
    ctx.strokeStyle = fg.value
    ctx.beginPath()
    ctx.moveTo(p1.x, p1.y)
    ctx.lineTo(p2.x, p2.y)
    ctx.stroke()
}

function screen(p){
    return{
        x: (p.x + 1)/2*game.width,
        y: (1 - (p.y + 1)/2)*game.height,
    }
}

function project({x, y, z}){
    const aspect = game.width / game.height
    return{
        x: x/z/aspect,
        y: y/z
    }
}

const FPS = 60

function translate_z({x, y, z}, dz){
    return {x, y, z: z + dz}
}

function rotate_xz({x, y, z}, angle){
    return{
        x: x * Math.cos(angle) - z * Math.sin(angle),
        y,
        z: x * Math.sin(angle) + z * Math.cos(angle)
    }
}

function rotate_yz({x, y, z}, angle){
    return{
        x,
        y: y * Math.cos(angle) - z * Math.sin(angle),
        z: y * Math.sin(angle) + z * Math.cos(angle)
    }
}


const keys = {
    ArrowUp: false,
    ArrowDown: false,
    ArrowLeft: false,
    ArrowRight: false,
    w: false,
    s:false,
}

window.addEventListener("keydown", e=> keys[e.key] = true)
window.addEventListener("keyup", e=> keys[e.key] = false)

function updateControls(dt){
    const speed = parseFloat(sliderSpeed.value)
    const moveSpeed = 2.0

    if (keys.ArrowLeft) angle_xz -= speed*dt
    if (keys.ArrowRight) angle_xz += speed*dt
    if (keys.ArrowDown) angle_yz -= speed*dt
    if (keys.ArrowUp) angle_yz += speed*dt

    if (keys.w) dz -= moveSpeed*dt
    if (keys.s) dz += moveSpeed*dt

}

let isDragging = false;
let lastTouchX = 0;
let lastTouchY = 0;

let rotationX = 0; 
let rotationY = 0;

game.addEventListener('touchstart', (e) => {
    isDragging = true;
    lastTouchX = e.touches[0].clientX;
    lastTouchY = e.touches[0].clientY;
}, { passive: false });

game.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    
    const touchX = e.touches[0].clientX;
    const touchY = e.touches[0].clientY;
    
    const deltaX = touchX - lastTouchX;
    const deltaY = touchY - lastTouchY;

    angle_xz += deltaX * 0.01;
    angle_yz += deltaY * 0.01;
    
    lastTouchX = touchX;
    lastTouchY = touchY;
    
    e.preventDefault();
}, { passive: false });

game.addEventListener('touchend', () => {
    isDragging = false;
});

let vs = [
    {x: 0.25, y: 0.25, z: 0.25},
    {x: -0.25, y: 0.25, z: 0.25},
    {x: -0.25, y: -0.25, z: 0.25},
    {x: 0.25, y: -0.25, z: 0.25},

    {x: 0.25, y: 0.25, z: -0.25},
    {x: -0.25, y: 0.25, z: -0.25},
    {x: -0.25, y: -0.25, z: -0.25},
    {x: 0.25, y: -0.25, z: -0.25},
]

let fs = [
    [0, 1, 2, 3],
    [4, 5, 6, 7],
    [0, 4],
    [1,5],
    [2, 6],
    [3,7]
]

function updateGeometry() {
    try {
        const newVs = JSON.parse(document.getElementById('vs-input').value);
        const newFs = JSON.parse(document.getElementById('fs-input').value);
        
        // Basic validation
        if (Array.isArray(newVs) && Array.isArray(newFs)) {
            vs = newVs;
            fs = newFs;
            console.log("Geometry updated successfully!");
        }
    } catch (e) {
        alert("Invalid JSON format. Please check your vertices and faces.");
    }
}


let dz = 1
let angle_xz = 0
let angle_yz = 0

function frame(){
    const dt = 1/FPS
    //dz += 1*dt
    //angle += 0.5*Math.PI*dt
    const idleToggle = document.getElementById("idle-toggle");
    if (idleToggle.checked && !isDragging && !keys.ArrowDown && 
        !keys.ArrowLeft && !keys.ArrowRight &&
        !keys.ArrowUp){
            const speed = parseFloat(sliderSpeed.value)
            angle_xz += 0.5*speed*dt
        }
    updateControls(dt)
    clear()
    // for(const v of vs){
    //     point(screen(project(translate_z(rotate_xz(v, angle), dz))))
    // }
    for(const f of fs){
        for(let i=0; i<f.length; ++i){
            const a = vs[f[i]]
            const b = vs[f[(i+1)%f.length]]
        line(
            screen(project(translate_z(rotate_xz(rotate_yz(a, angle_yz), angle_xz), dz))),
            screen(project(translate_z(rotate_xz(rotate_yz(b, angle_yz), angle_xz), dz)))
        )
        }
    }
    setTimeout(frame, 1000/FPS)
}
setTimeout(frame, 1000/FPS)