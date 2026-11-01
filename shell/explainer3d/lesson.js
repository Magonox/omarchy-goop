.pragma library

// The interpreter: plays a resolved scene (built by daemon/goop/explainer) at time t. Nothing here knows about any subject; it only knows
// the verbs: reveal, explode, spin, highlight, cutaway, label, flow, pulse, and a camera that follows keyframes.

function clamp(x) { return Math.max(0, Math.min(1, x)); }
function ramp(u) { u = clamp(u); return u * u * (3 - 2 * u); }
function lerp(a, b, u) { return a + (b - a) * u; }
var WAVE_SPEED = 2.2, WAVE_LIFE = 5.5, WAVE_EVERY = 0.9;

function prepare(scene) {
    var C = { finale: scene.finale || null,  scene: scene, idx: {}, reveal: [], ev: { spin: [], highlight: [], explode: [], cutaway: [], label: [], flow: [], pulse: [] }, bars: [], pulse: null };
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
            var settle = e.settle || 1.0;            // the finale takes longer to put the parts back together
            s.amt = Math.max(s.amt, ramp((t - e.t0) / 1.0) * (1 - ramp((t - (e.t1 - settle)) / settle)));
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

    // the finale: the assembled thing sets off as one body (a group transform), with effects streaming from it, then is gone
    var fin = C.finale, root = { pivot: [0, 0, 0], pos: [0, 0, 0], rot: [0, 0, 0] }, fx = [], env = null;
    if (fin) {
        var g = finaleMotion(fin, t);
        root = { pivot: fin.center, pos: [fin.center[0] + g.d[0], fin.center[1] + g.d[1], fin.center[2] + g.d[2]], rot: g.rot };
        parts.forEach(function (s) { s.alpha = Math.min(s.alpha, g.alpha); if (g.gone) s.vis = false; });
        fx = finaleParticles(fin, t);
        env = finaleEnv(fin, t);
    }

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
    if (pu && !(C.finale && t >= C.finale.t0)) {            // the ripples stop when the finale begins
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
    return { parts: parts, labels: labels, drops: drops, rings: rings, bars: bars, cam: cam, root: root, fx: fx, env: env };
}

// ---- the finale ----

// How far the whole body travels before it is out of the picture, for each motion.
function finaleReach(f) {
    var R = f.radius;
    return f.motion === "drive" ? 3.6 * R + 10 : f.motion === "sink" ? 2.4 * R + 6 : 2.6 * R + 8;
}

// The pose of the assembled body at time t: {d: offset, rot: degrees, alpha, gone}. Before t_go it sits still; the engine idles, then it goes.
function finaleMotion(f, t) {
    var tau = t - f.t_go, D = f.dur, R = f.radius, h = f.heading, m = f.motion, out = { d: [0, 0, 0], rot: [0, 0, 0], alpha: 1, gone: false };
    if (tau < 0) return out;
    if (tau >= D + 0.3) out.gone = true;
    tau = Math.min(tau, D);
    var lift = m === "launch" ? 1.3 : m === "sink" ? 0.8 : 0.9, T = D - lift, reach = finaleReach(f);
    if (tau < lift) {           // idling: a rocket shakes, a truck revs, a submarine bobs
        var wob = m === "sink" ? 0.04 * R * Math.sin(tau * 4) : 0.015 * R * Math.sin(tau * 55) * Math.min(1, tau / 0.4);
        out.d = m === "sink" ? [0, wob, 0] : [wob, 0, wob * 0.6];
        return out;
    }
    var u = tau - lift, p = u / T, s;
    if (m === "sink") s = reach * ramp(p);
    else s = reach * p * p;     // speeding up the whole way
    out.d = [h[0] * s, h[1] * s, h[2] * s];
    if (m === "launch") out.rot = [0, 40 * p, 0];                                              // a slow roll as it climbs
    else if (m === "drive") { out.d[1] += 0.04 * R * Math.sin(u * 11) * ramp(u / 0.8); out.rot = [0, 0, -2 * ramp(u / 1.2)]; }   // bouncing along, nose up
    else if (m === "sink") { out.rot = [0, 0, 7 * Math.sin(u * 1.4) * ramp(u / 0.6)]; out.alpha = 1 - ramp((p - 0.45) / 0.55); }  // swaying down, fading into the dark
    else if (m === "fly") out.rot = [0, 0, 14 * ramp(u / 1.5)];
    return out;
}

function frac(x) { return x - Math.floor(x); }

// where the effect streams from, in the assembled position: the emitter part if the story named one
function finaleAnchor(f) {
    var c = f.center, R = f.radius, em = f.emitter, h = f.heading;
    if (f.motion === "launch") return [em ? em[0] : c[0], f.bottom, em ? em[2] : c[2]];
    if (f.motion === "drive") return [em ? em[0] : c[0] - h[0] * R * 0.8, f.bottom + 0.15, em ? em[2] : c[2]];
    if (f.motion === "sink") return [c[0], c[1] + (f.top - c[1]) * 0.6, c[2]];
    return em ? [em[0], em[1], em[2]] : [c[0] - R * 0.8, c[1], c[2]];
}

var FX = {
    flame:    { rate: 28, life: 0.55, from: -0.9, c: [1.0, 0.62, 0.15], s0: 1.1, s1: 0.2, a: 0.95, em: 1.1, spread: 0.4, trail: 3.4 },
    smoke:    { rate: 26, life: 2.2, from: -0.5, c: [0.72, 0.72, 0.75], s0: 0.35, s1: 1.5, a: 0.32, em: 0, spread: 2.6, trail: 0 },
    bubbles:  { rate: 16, life: 3.4, from: 0.0, c: [0.75, 0.92, 1.0], s0: 0.3, s1: 0.5, a: 0.7, em: 0.2, spread: 0.9, rise: 1.2 },
    dust:     { rate: 24, life: 1.4, from: 0.2, c: [0.78, 0.68, 0.52], s0: 0.35, s1: 1.2, a: 0.45, em: 0, spread: 0.7, trail: 0 },
    contrail: { rate: 22, life: 1.9, from: 0.9, c: [0.95, 0.97, 1.0], s0: 0.5, s1: 1.4, a: 0.6, em: 0.1, spread: 0.15, trail: 0 }
};

function finaleParticles(f, t) {
    var out = [], a0 = finaleAnchor(f), R = f.radius, k = Math.max(0.6, Math.min(2, R / 6)), h = f.heading;
    f.effects.forEach(function (name) {
        var e = FX[name], ts0 = f.t_go + e.from, n0 = Math.max(0, Math.ceil((t - e.life - ts0) * e.rate)), n1 = Math.floor((t - ts0) * e.rate);
        for (var n = n0; n <= n1; n++) {
            var ts = ts0 + n / e.rate;
            if (ts > f.t_go + f.dur || ts < ts0) continue;
            var age = t - ts, u = age / e.life, d = finaleMotion(f, ts).d;
            var r1 = frac(Math.sin(n * 12.9898 + name.length) * 43758.5453) - 0.5, r2 = frac(Math.sin(n * 78.233 + 1.3) * 43758.5453) - 0.5;
            var vx = -h[0] * (e.trail || 0) + (name === "dust" ? -h[0] * 1.8 : 0) + r1 * e.spread * (name === "smoke" ? 1.2 : 1);
            var vy = -h[1] * (e.trail || 0) + (e.rise || 0) + (name === "dust" ? 0.9 : name === "smoke" ? 0.35 : 0);
            var vz = r2 * e.spread * (name === "smoke" ? 1.2 : 1);
            var size = lerp(e.s0, e.s1, u) * k * 0.01;
            out.push({ x: a0[0] + d[0] + vx * age, y: a0[1] + d[1] + vy * age, z: a0[2] + d[2] + vz * age, s: size,
                       r: e.c[0], g: e.c[1] * (name === "flame" ? 1 - 0.6 * u : 1), b: e.c[2], a: e.a * (1 - u) * Math.min(1, age / 0.1), em: e.em * (1 - 0.6 * u) });
        }
    });
    return out.length > 96 ? out.slice(out.length - 96) : out;
}

// the prop that sets the scene: a launch pad, a road, or the surface of the sea
function finaleEnv(f, t) {
    if (f.env === "none") return null;
    var a = ramp((t - f.t0 - 0.3) / 1.2) * ramp((f.t_go + f.dur + 1.2 - t) / 1.0);
    if (a < 0.01) return null;
    var c = f.center, R = f.radius;
    if (f.env === "pad") return { pos: [c[0], f.bottom - 0.12, c[2]], size: [R * 1.6, 0.2, R * 1.6], color: [0.26, 0.28, 0.33], a: a };
    if (f.env === "road") return { pos: [c[0] + R * 1.2, f.bottom - 0.08, c[2]], size: [R * 5.5, 0.12, R * 1.1], color: [0.16, 0.17, 0.2], a: a };
    return { pos: [c[0], f.bottom + 0.45 * (f.top - f.bottom), c[2]], size: [R * 6.5, 0.05, R * 3.5], color: [0.2, 0.5, 0.9], a: a * 0.34 };
}
