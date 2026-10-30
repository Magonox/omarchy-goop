.pragma library
.import "engine3d.js" as E

// Hand-written storyboard for "how a hydroelectric dam works": the first thing the renderer plays. Parts come from math, not assets.
var DURATION = 28;

var M = {
    ground: E.box(15, 0.4, 4.8),
    reservoir: E.box(6.2, 2.4, 4.0),
    wall: E.prism([[-0.6, 0], [1.0, 0], [0.1, 3.0], [-0.6, 3.0]], -2.2, 2.2),
    river: E.box(5.4, 0.4, 3.0),
    penstock: E.pipe([-0.9, 0.9, 0], [1.7, 0.55, 0], 0.26, 14),
    disc: E.cylinder(0.72, 0.3, 18),
    shaft: E.cylinder(0.1, 1.0, 10),
    generator: E.cylinder(0.62, 0.8, 18),
    blade: E.box(0.58, 0.05, 0.16, 0.34, 0, 0)
};

var PATH = [[-3.2, 1.1, 0], [-1.2, 0.9, 0], [1.7, 0.55, 0], [2.1, 0.5, 0], [3.2, 0.3, 0], [5.6, 0.32, 0]];
function along(s) {        // a point at fraction s (0..1) of the path, by segment length
    var lens = [], total = 0, i;
    for (i = 0; i < PATH.length - 1; i++) { var d = Math.hypot(PATH[i + 1][0] - PATH[i][0], PATH[i + 1][1] - PATH[i][1], PATH[i + 1][2] - PATH[i][2]); lens.push(d); total += d; }
    var t = s * total;
    for (i = 0; i < lens.length; i++) {
        if (t <= lens[i] || i === lens.length - 1) { var u = Math.min(1, t / lens[i]); return [PATH[i][0] + (PATH[i + 1][0] - PATH[i][0]) * u, PATH[i][1] + (PATH[i + 1][1] - PATH[i][1]) * u, PATH[i][2] + (PATH[i + 1][2] - PATH[i][2]) * u]; }
        t -= lens[i];
    }
    return PATH[PATH.length - 1];
}

function clamp(x) { return Math.max(0, Math.min(1, x)); }
function ramp(t, a, b) { var u = clamp((t - a) / (b - a)); return u * u * (3 - 2 * u); }     // smooth 0..1 between a and b
function fade(t, a, b, c, d) { return ramp(t, a, b) * (1 - ramp(t, c, d)); }                  // in at a..b, out at c..d

function scene(t) {
    var outro = 1 - ramp(t, 25, 27.5), intro = ramp(t, 0, 1.5);
    var wallA = (1 - 0.78 * ramp(t, 4.5, 6.5) + 0.78 * ramp(t, 21, 23)) * ramp(t, 0.8, 2.2) * outro;
    var explode = 1.7 * ramp(t, 11, 13.5) * (1 - ramp(t, 18, 20.5));
    var spin = Math.max(0, t - 7), angle = 0.8 * spin * (1 + 0.6 * ramp(t, 7, 11)) * 3;
    var pipeA = ramp(t, 4.5, 6) * outro, flowOn = ramp(t, 6, 7) * outro, genGlow = fade(t, 12.5, 13.5, 17, 18.5);
    var cam = { target: [0.8, 1.1, 0], yaw: (-0.42 + 0.7 * ramp(t, 1, 24)), pitch: 0.4, dist: 30, f: 1010 };
    var cx = 2.1, objects = [
        { mesh: M.ground, pos: [0.5, -0.2, 0], color: [74, 92, 84], alpha: 0.95 * intro * outro, layer: 0 },
        { mesh: M.wall, pos: [0, 0, 0], color: [196, 198, 204], alpha: wallA, glow: fade(t, 2, 3, 4, 5) },
        { mesh: M.penstock, pos: [0, 0, 0], color: [214, 126, 62], alpha: pipeA, glow: fade(t, 5, 6, 8, 9) },
        { mesh: M.disc, pos: [cx, 0.4, 0], color: [96, 108, 132], alpha: pipeA },
        { mesh: M.shaft, pos: [cx, 1.0 + explode * 0.5, 0], color: [150, 156, 170], alpha: pipeA },
        { mesh: M.generator, pos: [cx, 1.9 + explode, 0], color: [214, 70, 70], alpha: pipeA, glow: genGlow },
        { mesh: M.reservoir, pos: [-3.7, 1.2, 0], color: [70, 150, 225], alpha: 0.5 * ramp(t, 0.4, 1.6) * outro, layer: 2 },
        { mesh: M.river, pos: [5.4, 0.2, 0], color: [74, 158, 228], alpha: 0.5 * ramp(t, 14, 15.5) * outro, layer: 2 }
    ];
    for (var k = 0; k < 8; k++) objects.push({ mesh: M.blade, pos: [cx, 0.62, 0], rotY: angle + k * Math.PI / 4, color: [226, 230, 238], alpha: pipeA });

    var particles = [];
    for (var i = 0; i < 34; i++) {
        var s = (t * 0.075 + i / 34) % 1, p = along(s), squeeze = 1 - 0.85 * ramp(s, 0.05, 0.3) * (1 - ramp(s, 0.62, 0.7));
        particles.push({ p: [p[0], p[1] + ((i % 5) - 2) * 0.13 * squeeze, p[2] + (((i * 7) % 5) - 2) * 0.22 * squeeze], r: 0.09,
                         color: [150, 210, 255], alpha: flowOn * (0.4 + 0.6 * ramp(wallA < 0.5 ? 1 : 0, 0, 1)) * (s > 0.12 && s < 0.5 ? (wallA < 0.5 ? 1 : 0.15) : 1) });
    }
    var labels = [
        { text: "Reservoir", at: [-3.7, 2.4, 1.9], dy: -40, alpha: fade(t, 1.5, 2.5, 6, 7) },
        { text: "Dam wall", at: [-0.3, 3.0, 2.2], dy: -34, alpha: fade(t, 2.5, 3.5, 6.5, 7.5) },
        { text: "Penstock", at: [0.4, 0.75, 0], dx: -10, dy: 52, alpha: fade(t, 5.5, 6.5, 14, 15) },
        { text: "Turbine", at: [cx + 0.7, 0.55, 0.3], dx: 70, dy: 40, alpha: fade(t, 8.5, 9.5, 18, 19) },
        { text: "Generator", at: [cx + 0.6, 1.9 + explode, 0], dx: 90, dy: -30, alpha: fade(t, 12, 13, 19, 20) },
        { text: "River", at: [5.4, 0.45, 1.4], dy: -44, alpha: fade(t, 15, 16, 24, 25) }
    ];
    return { cam: cam, objects: objects, particles: particles, labels: labels };
}
