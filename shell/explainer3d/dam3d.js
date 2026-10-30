.pragma library
.import "meshes.js" as M

// The hydroelectric dam storyboard for the 3D renderer: PARTS describe what exists (shape, material, home position); state(t) says what each
// part, the camera, the water drops and the labels are doing at time t. Everything is code: no model files. Units are metres.
var DURATION = 30;
var TURBINE = [3.9, 0.9, 0];

function clamp(x) { return Math.max(0, Math.min(1, x)); }
function ramp(t, a, b) { var u = clamp((t - a) / (b - a)); return u * u * (3 - 2 * u); }
function fade(t, a, b, c, d) { return ramp(t, a, b) * (1 - ramp(t, c, d)); }
function lerp(a, b, u) { return a + (b - a) * u; }

function hill(x, z) {      // a cutaway diorama: the valley rises behind the dam, the near side stays low so nothing blocks the view
    var back = z < 0 ? ramp(-z, 2.2, 8.5) : 0, front = z > 0 ? 0.35 * ramp(z, 3.5, 6.5) : 0;
    var lump = 0.5 * Math.sin(x * 0.55 + z * 0.8) + 0.3 * Math.sin(x * 1.3 - z * 0.45) + 0.2 * Math.sin(z * 1.7 + x * 0.3);
    return 6.2 * back + front + lump * (0.1 + 0.9 * back) - 0.05;
}

var WATER = [96, 170, 235], CONCRETE = [190, 190, 196], STEEL = [118, 130, 152], COPPER = [200, 112, 62], ORANGE = [225, 130, 60];
var PARTS = [
    { id: "terrain", mesh: function () { return M.terrain(-12, 15, -9, 6.5, 54, 31, hill); }, pos: [0, 0, 0], color: [96, 118, 82], rough: 0.95, metal: 0 },
    { id: "skirt", mesh: function () { return M.skirt(-12, 15, -9, 6.5, 54, 31, hill, -1.6); }, pos: [0, 0, 0], color: [128, 98, 74], rough: 0.95, metal: 0 },
    { id: "reservoir", mesh: function () { return M.box(9.9, 2.6, 10.8, 0); }, pos: [-5.55, 0.02, 0], color: WATER, rough: 0.05, metal: 0, blend: 0.55 },
    { id: "wall", mesh: function () { return M.prism([[-0.6, 0], [1.1, 0], [0.25, 3.4], [-0.6, 3.4]], -6.3, 6.3); }, pos: [0, 0, 0], color: [172, 174, 182], rough: 0.9, metal: 0, blend: 1 },
    { id: "crest", mesh: function () { return M.box(1.3, 0.22, 12.6, 0); }, pos: [-0.2, 3.4, 0], color: [170, 170, 178], rough: 0.85, metal: 0 },
    { id: "gate1", mesh: function () { return M.box(0.28, 1.1, 1.7, 0); }, pos: [-0.74, 2.3, -3.3], color: [70, 78, 92], rough: 0.5, metal: 0.6 },
    { id: "gate2", mesh: function () { return M.box(0.28, 1.1, 1.7, 0); }, pos: [-0.74, 2.3, 0], color: [70, 78, 92], rough: 0.5, metal: 0.6 },
    { id: "gate3", mesh: function () { return M.box(0.28, 1.1, 1.7, 0); }, pos: [-0.74, 2.3, 3.3], color: [70, 78, 92], rough: 0.5, metal: 0.6 },
    { id: "powerhouse", mesh: function () { return M.box(3.6, 3.4, 4.6, 0); }, pos: [3.9, 0, 0], color: [214, 208, 196], rough: 0.8, metal: 0, blend: 1 },
    { id: "roof", mesh: function () { return M.box(4.0, 0.28, 5.0, 0); }, pos: [3.9, 3.4, 0], color: [120, 74, 66], rough: 0.7, metal: 0, blend: 1 },
    { id: "penstock", mesh: function () { return M.pipe([-1.5, 1.8, 0], [3.0, 0.9, 0], 0.4, 24); }, pos: [0, 0, 0], color: ORANGE, rough: 0.35, metal: 0.55 },
    { id: "flange1", mesh: function () { return M.torus(0.42, 0.07, 28, 10); }, pos: [-0.9, 1.68, 0], rot: [0, 0, 79], color: [150, 160, 176], rough: 0.3, metal: 0.8 },
    { id: "flange2", mesh: function () { return M.torus(0.42, 0.07, 28, 10); }, pos: [0.9, 1.33, 0], rot: [0, 0, 79], color: [150, 160, 176], rough: 0.3, metal: 0.8 },
    { id: "flange3", mesh: function () { return M.torus(0.42, 0.07, 28, 10); }, pos: [2.5, 1.0, 0], rot: [0, 0, 79], color: [150, 160, 176], rough: 0.3, metal: 0.8 },
    { id: "casing", mesh: function () { return M.torus(1.15, 0.3, 40, 14); }, pos: [TURBINE[0], TURBINE[1], TURBINE[2]], color: STEEL, rough: 0.35, metal: 0.75 },
    { id: "runner", mesh: function () { return M.cyl(0.9, 0.22, 28, -0.11); }, pos: [TURBINE[0], TURBINE[1], TURBINE[2]], color: [160, 172, 190], rough: 0.25, metal: 0.85 },
    { id: "shaft", mesh: function () { return M.cyl(0.11, 1.2, 14, 0); }, pos: [TURBINE[0], 0.9, 0], color: [190, 196, 208], rough: 0.2, metal: 0.9, lift: 0.5 },
    { id: "generator", mesh: function () { return M.cyl(0.98, 1.2, 36, 0); }, pos: [TURBINE[0], 1.9, 0], color: [196, 60, 66], rough: 0.4, metal: 0.45, lift: 1, glowable: true },
    { id: "coil1", mesh: function () { return M.torus(0.99, 0.07, 36, 10); }, pos: [TURBINE[0], 2.2, 0], color: COPPER, rough: 0.28, metal: 0.95, lift: 1, glowable: true },
    { id: "coil2", mesh: function () { return M.torus(0.99, 0.07, 36, 10); }, pos: [TURBINE[0], 2.65, 0], color: COPPER, rough: 0.28, metal: 0.95, lift: 1, glowable: true },
    { id: "coil3", mesh: function () { return M.torus(0.99, 0.07, 36, 10); }, pos: [TURBINE[0], 3.0, 0], color: COPPER, rough: 0.28, metal: 0.95, lift: 1, glowable: true },
    { id: "river", mesh: function () { return M.box(8.2, 0.36, 3.8, 0); }, pos: [10.9, 0.02, 0], color: WATER, rough: 0.05, metal: 0, blend: 0.55 },
    { id: "tower", mesh: function () { return M.prism([[-0.55, 0], [0.55, 0], [0.16, 5.2], [-0.16, 5.2]], -0.14, 0.14); }, pos: [10.0, 0, -3.6], color: [140, 148, 160], rough: 0.5, metal: 0.8 },
    { id: "arm", mesh: function () { return M.box(2.4, 0.14, 0.14, 0); }, pos: [10.0, 4.6, -3.6], color: [140, 148, 160], rough: 0.5, metal: 0.8 },
    { id: "line", mesh: function () { return M.pipe([3.9, 3.8, 0], [10.0, 4.7, -3.6], 0.045, 8); }, pos: [0, 0, 0], color: [30, 30, 36], rough: 0.5, metal: 0.4 }
];
for (var k = 0; k < 12; k++) PARTS.push({ id: "blade" + k, blade: k, mesh: function () { return M.box(0.78, 0.06, 0.26, 0, 0.5); }, pos: [TURBINE[0], TURBINE[1] + 0.13, TURBINE[2]], color: [232, 236, 244], rough: 0.2, metal: 0.9 });
var IDX = {}; PARTS.forEach(function (p, i) { IDX[p.id] = i; });

var cache = {};
function meshOf(i) { return cache[i] || (cache[i] = PARTS[i].mesh()); }
function positions(i) { return M.vecs(meshOf(i).p); }
function normals(i) { return M.vecs(meshOf(i).n); }
function indexes(i) { return meshOf(i).i; }

var PATH = [[-5.6, 1.3, 0], [-3.2, 1.5, 0], [-1.5, 1.8, 0], [3.0, 0.9, 0], [3.9, 0.9, 0], [4.9, 0.55, 0], [7.2, 0.42, 0], [14.2, 0.42, 0]];
function along(path, s) {
    var lens = [], total = 0, i;
    for (i = 0; i < path.length - 1; i++) { var d = Math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1], path[i + 1][2] - path[i][2]); lens.push(d); total += d; }
    var t = s * total;
    for (i = 0; i < lens.length; i++) {
        if (t <= lens[i] || i === lens.length - 1) { var u = Math.min(1, t / lens[i]); return [lerp(path[i][0], path[i + 1][0], u), lerp(path[i][1], path[i + 1][1], u), lerp(path[i][2], path[i + 1][2], u)]; }
        t -= lens[i];
    }
    return path[path.length - 1];
}
var LINE = [[3.9, 3.8, 0], [10.0, 4.7, -3.6]];

function state(t) {
    var outro = 1 - ramp(t, 27, 29.5);
    var cut = ramp(t, 5, 6.8) * (1 - ramp(t, 22, 24));            // the cutaway: wall and powerhouse go see-through
    var explode = 2.9 * ramp(t, 11.5, 14) * (1 - ramp(t, 19, 21.5));
    var spin = Math.max(0, t - 8), angle = (spin * (1 + 0.7 * ramp(t, 8, 12)) * 150) % 360;
    var pen = ramp(t, 5, 6.2), electric = ramp(t, 15, 16);
    var glow = fade(t, 13, 14, 18, 19.5);
    var zoom = ramp(t, 7, 10) * (1 - ramp(t, 20, 23.5));                // close-up on the machinery, then back out

    var parts = PARTS.map(function (p, i) {
        var s = { vis: true, sx: 1, sy: 1, sz: 1, dx: 0, dy: 0, dz: 0, rotY: 0, alpha: 1, glow: 0 };
        var g = 1;
        switch (p.id) {
            case "terrain": case "skirt": g = ramp(t, 0, 2.2) * (1 - zoom); s.sy = Math.max(0.001, g); s.vis = g > 0.03; break;    // the ground sinks away during the close-up
            case "reservoir": g = ramp(t, 1.4, 3.2); s.sy = Math.max(0.001, g); break;
            case "wall": g = ramp(t, 1.8, 3.6); s.sy = Math.max(0.001, g); s.alpha = lerp(1, 0.2, cut); break;
            case "crest": case "gate1": case "gate2": case "gate3": g = ramp(t, 3.2, 4.2); s.sx = s.sy = s.sz = Math.max(0.001, g); break;
            case "powerhouse": g = ramp(t, 2.4, 4.2); s.sy = Math.max(0.001, g); s.alpha = lerp(1, 0.16, cut); break;
            case "roof": g = ramp(t, 3.4, 4.4); s.sx = s.sy = s.sz = Math.max(0.001, g); s.dy = (1 - g) * 2; s.alpha = lerp(1, 0.16, cut); break;
            case "river": g = ramp(t, 16, 17.6); s.sy = Math.max(0.001, g); break;
            case "tower": case "arm": g = ramp(t, 15, 16.2); s.sx = s.sy = s.sz = Math.max(0.001, g); break;
            case "line": g = electric; s.vis = g > 0.02; break;
            default:
                if (p.id.indexOf("flange") === 0 || p.id === "penstock" || p.id === "casing" || p.id === "runner" || p.id.indexOf("blade") === 0 || p.id === "shaft" || p.id === "generator" || p.id.indexOf("coil") === 0) {
                    g = pen; s.sx = s.sy = s.sz = Math.max(0.001, g);
                }
        }
        if (p.lift) s.dy = explode * p.lift;
        if (p.blade !== undefined) s.rotY = angle + p.blade * 30;
        if (p.glowable) s.glow = glow;
        s.sx *= outro; s.sy *= outro; s.sz *= outro;
        s.vis = s.vis && (outro > 0.01) && s.sy > 0.002;
        return s;
    });

    var drops = [], n = 46, flow = ramp(t, 6.6, 7.6) * outro;
    for (var i = 0; i < n; i++) {
        var s = (t * 0.06 + i / n) % 1, p = along(PATH, s), squeeze = 1 - 0.9 * ramp(s, 0.04, 0.22) * (1 - ramp(s, 0.36, 0.44));
        drops.push({ x: p[0], y: p[1] + ((i % 5) - 2) * 0.22 * squeeze, z: p[2] + (((i * 7) % 5) - 2) * 0.5 * squeeze, vis: flow > 0.05 ? 1 : 0, s: 0.0026 * flow });
    }
    var sparks = [];
    for (var j = 0; j < 14; j++) {
        var u = (t * 0.28 + j / 14) % 1;
        sparks.push({ x: lerp(LINE[0][0], LINE[1][0], u), y: lerp(LINE[0][1], LINE[1][1], u) + 0.1, z: lerp(LINE[0][2], LINE[1][2], u), s: 0.0018 * electric * outro });
    }

    var cam = {
        target: [lerp(1.6, TURBINE[0] - 0.2, zoom), lerp(1.2, 1.9, zoom), -1.0], dist: lerp(36, 16, zoom),
        yaw: lerp(-24, 18, ramp(t, 1, 27)), pitch: lerp(32, 27, zoom)
    };
    var labels = [
        { text: "Reservoir", at: [-6.4, 2.7, 4.2], dx: 0, dy: -46, a: fade(t, 3.2, 4.2, 6.2, 7.2) },
        { text: "Dam wall", at: [0.5, 3.5, 5.2], dx: 10, dy: -44, a: fade(t, 4.2, 5.2, 7, 8) },
        { text: "Penstock", at: [0.9, 1.4, 0], dx: -20, dy: 62, a: fade(t, 6, 7, 11, 12) },
        { text: "Turbine", at: [TURBINE[0] + 1.2, 0.9, 0.5], dx: 90, dy: 40, a: fade(t, 8.2, 9.2, 13, 14.2) },
        { text: "Generator", at: [TURBINE[0] + 1.0, 2.8 + explode, 0], dx: 110, dy: -28, a: fade(t, 12.2, 13.2, 20, 21) },
        { text: "Power line", at: [7.0, 4.2, -1.8], dx: 0, dy: -50, a: fade(t, 15.5, 16.5, 23, 24) },
        { text: "River", at: [10.0, 0.5, 1.8], dx: 20, dy: 50, a: fade(t, 17, 18, 25, 26) }
    ];
    return { parts: parts, drops: drops, sparks: sparks, cam: cam, labels: labels, electric: electric };
}
