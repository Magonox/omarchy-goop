.pragma library

// The interpreter: plays a resolved scene (built by daemon/goop/explainer) at time t. Nothing here knows about any subject; it only knows
// the verbs: reveal, explode, spin, highlight, cutaway, label, flow, pulse, and a camera that follows keyframes.

function clamp(x) { return Math.max(0, Math.min(1, x)); }
function ramp(u) { u = clamp(u); return u * u * (3 - 2 * u); }
function lerp(a, b, u) { return a + (b - a) * u; }
var WAVE_SPEED = 2.2, WAVE_LIFE = 5.5, WAVE_EVERY = 0.9;

function prepare(scene) {
    var C = { scene: scene, idx: {}, reveal: [], ev: { spin: [], highlight: [], explode: [], cutaway: [], label: [], flow: [], pulse: [] }, bars: [], pulse: null };
    scene.parts.forEach(function (p, i) { C.idx[p.id] = i; C.reveal.push(undefined); });
    scene.events.forEach(function (e) {
        if (e.type === "reveal") {
            e.parts.forEach(function (id) { var i = C.idx[id]; if (C.reveal[i] === undefined || e.t0 < C.reveal[i]) C.reveal[i] = e.t0; });
        } else {
            var set = {};
            (e.parts || []).forEach(function (id) { set[C.idx[id]] = true; });
            var copy = {}; for (var k in e) copy[k] = e[k];
            copy.set = set;
            C.ev[e.type].push(copy);
        }
    });
    scene.parts.forEach(function (p, i) { if (p.signal !== undefined) for (var k = 0; k < 4; k++) C.bars.push({ part: i, k: k }); });
    C.pulse = C.ev.pulse.length ? C.ev.pulse[0] : null;
    return C;
}

function material(part, role, dyn) {
    var m = part.material, c = m.color.slice(), a = 1, em = [0, 0, 0], metal = m.metal, rough = m.rough, lit = role === "main" || role === "accent";
    var kind = role.charAt(1) === ":" ? role.charAt(0) : "";                  // custom parts: m: solid, g: glass, w: glow, then the material's name
    if (kind) {
        var pm = (part.palette && part.palette[role.slice(2)]) || m;
        c = pm.color.slice(); metal = pm.metal; rough = pm.rough;
        if (kind === "w") { em = [c[0] / 255 * 0.9, c[1] / 255 * 0.9, c[2] / 255 * 0.9]; a = 0.9; metal = 0; }
        else if (kind === "m") lit = true;
        role = kind === "m" ? "main" : kind === "g" ? "glass" : "glow";
        if (kind === "w") { return { r: c[0] / 255, g: c[1] / 255, b: c[2] / 255, metal: metal, rough: rough, alpha: a, er: em[0], eg: em[1], eb: em[2] }; }
    }
    switch (role) {
    case "accent": c = c.map(function (x) { return x * 0.62; }); break;
    case "dark": c = [90, 98, 116]; metal = 0.25; rough = 0.45; break;
    case "blade": c = c.map(function (x) { return Math.min(255, x * 1.2 + 24); }); metal = 0.3; rough = 0.35; break;
    case "glass": a = 0.3; c = c.map(function (x) { return Math.min(255, x * 0.55 + 100); }); metal = 0; rough = 0.08; break;
    case "glow": c = [255, 150, 60]; em = [0.9, 0.4, 0.1]; a = 0.88; metal = 0; break;
    case "screen": c = [40, 72, 116]; em = [0.12, 0.34, 0.8]; metal = 0.1; rough = 0.2; break;
    case "led": c = [60, 220, 110]; em = [0.08, 0.8, 0.25]; break;
    case "floor": c = [104, 114, 134]; a = 0.3; metal = 0; rough = 0.9; break;
    }
    if (role === "main" && m.alpha !== undefined) a *= m.alpha;
    if (lit || role === "blade") {
        a *= dyn.alpha;
        em = [em[0] + c[0] / 255 * 0.5 * dyn.glow, em[1] + c[1] / 255 * 0.5 * dyn.glow, em[2] + c[2] / 255 * 0.5 * dyn.glow];
    }
    return { r: c[0] / 255, g: c[1] / 255, b: c[2] / 255, metal: metal, rough: rough, alpha: a, er: em[0], eg: em[1], eb: em[2] };
}

function state(C, t) {
    var scene = C.scene, ev = C.ev;
    var parts = scene.parts.map(function (p, i) {
        var s = { vis: false, k: 0, dx: 0, dy: 0, dz: 0, spin: 0, glow: 0, alpha: 1, amt: 0 };
        var r = C.reveal[i];
        if (r !== undefined) {
            var u = clamp((t - r) / 0.9);
            s.k = ramp(u) * (1 + 0.07 * Math.sin(Math.PI * u));
            s.vis = s.k > 0.003;
        }
        ev.spin.forEach(function (e) {
            if (!e.set[i]) return;
            var age = t - e.t0;
            if (age > 0) s.spin += e.rate * (age < 1.5 ? age * age / 3 : age - 0.75);
        });
        ev.explode.forEach(function (e) {
            if (!e.set[i]) return;
            s.amt = Math.max(s.amt, ramp((t - e.t0) / 1.0) * (1 - ramp((t - (e.t1 - 1.0)) / 1.0)));
        });
        ev.highlight.forEach(function (e) {
            if (!e.set[i]) return;
            s.glow = Math.max(s.glow, Math.min(ramp((t - e.t0) / 0.6), ramp((e.t1 - t) / 0.5)) * (0.75 + 0.25 * Math.sin(t * 5)));
        });
        ev.cutaway.forEach(function (e) {
            if (!e.set[i]) return;
            var f = ramp((t - e.t0) / 0.8) * (1 - ramp((t - (e.t1 - 0.6)) / 0.8));
            s.alpha = Math.min(s.alpha, 1 - f * (1 - e.alpha));
        });
        s.dx = p.explode[0] * s.amt; s.dy = p.explode[1] * s.amt; s.dz = p.explode[2] * s.amt;
        return s;
    });

    var outro = ramp((scene.duration - t) / 1.6);      // the whole model shrinks away at the very end
    parts.forEach(function (s) { s.k *= outro; if (s.k < 0.003) s.vis = false; });
    var labels = [];
    ev.label.forEach(function (e) {
        var a = Math.min(ramp((t - e.t0) / 0.5), ramp((e.t1 - t) / 0.5));
        if (a < 0.02) return;
        e.parts.forEach(function (id) {
            var i = C.idx[id], p = scene.parts[i], s = parts[i];
            if (!s.vis) return;
            labels.push({ text: p.label, a: a * Math.min(1, s.k) * outro, at: [p.pos[0] + s.dx, p.pos[1] + s.dy + p.radius * 0.85, p.pos[2] + s.dz] });
        });
    });

    var drops = [];
    ev.flow.forEach(function (e) {
        var fade = Math.min(ramp((t - e.t0) / 0.6), ramp((e.t1 - t) / 0.6));
        if (fade < 0.02) return;
        var path = scene.paths[e.path], n = 16;
        for (var j = 0; j < n; j++) {
            var s = ((t - e.t0) * 0.22 + j / n) % 1;
            drops.push({ x: lerp(path[0][0], path[1][0], s) + 0, y: lerp(path[0][1], path[1][1], s) + ((j % 5) - 2) * 0.13, z: lerp(path[0][2], path[1][2], s) + (((j * 7) % 5) - 2) * 0.13,
                         s: 0.0024 * fade, r: e.color[0] / 255, g: e.color[1] / 255, b: e.color[2] / 255 });
        }
    });

    var rings = [], pu = C.pulse;
    if (pu) {
        var src = scene.parts[C.idx[pu.source]], first = Math.max(0, Math.floor((t - pu.t0 - WAVE_LIFE) / WAVE_EVERY)), last = Math.floor((t - pu.t0) / WAVE_EVERY);
        for (var n2 = first; n2 <= last; n2++) {
            var age = t - pu.t0 - n2 * WAVE_EVERY;
            if (age < 0 || age > WAVE_LIFE) continue;
            rings.push({ x: src.pos[0], y: 0.08, z: src.pos[2], radius: 0.3 + WAVE_SPEED * age, a: Math.pow(1 - age / WAVE_LIFE, 1.3) * 0.8 });
        }
    }

    var bars = C.bars.map(function (b) {
        var p = scene.parts[b.part], s = parts[b.part], h = 0.1 + 0.09 * b.k;
        var reached = pu && t >= pu.t0 + p.distance / WAVE_SPEED + 0.3;
        var lit = reached && b.k < p.signal, col = [[240, 80, 70], [244, 150, 60], [190, 214, 70], [80, 220, 110]][p.signal - 1];
        return { x: p.pos[0] + (b.k - 1.5) * 0.14, y: p.pos[1] + p.shape.h / 2 + 0.22 + h / 2, z: p.pos[2], w: 0.1, h: h, vis: s.vis,
                 r: (lit ? col[0] : 62) / 255, g: (lit ? col[1] : 68) / 255, b: (lit ? col[2] : 82) / 255, em: lit ? 0.9 : 0 };
    });

    var cams = scene.camera, i = 0;
    while (i + 1 < cams.length && cams[i + 1].t <= t) i++;
    var b2 = cams[i], a2 = cams[Math.max(0, i - 1)], u2 = ramp((t - b2.t) / 1.8);
    var cam = { target: [0, 1, 2].map(function (k) { return lerp(a2.target[k], b2.target[k], u2); }), dist: lerp(a2.dist, b2.dist, u2),
                yaw: lerp(a2.yaw, b2.yaw, u2) + 2.5 * Math.sin(t * 0.17), pitch: lerp(a2.pitch, b2.pitch, u2) };
    return { parts: parts, labels: labels, drops: drops, rings: rings, bars: bars, cam: cam };
}
