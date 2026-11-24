.pragma library

// The interpreter: plays a resolved scene (built by daemon/goop/explainer) at time t. Nothing here knows about any subject; it only knows
// the verbs: reveal, explode, spin, highlight, cutaway, label, flow, pulse, and a camera that follows keyframes.

function clamp(x) { return Math.max(0, Math.min(1, x)); }
function ramp(u) { u = clamp(u); return u * u * (3 - 2 * u); }
function lerp(a, b, u) { return a + (b - a) * u; }
var WAVE_SPEED = 2.2, WAVE_LIFE = 5.5, WAVE_EVERY = 0.9;

// The real size of a part: the box around its mesh (after the part's own scale), in the part's own frame, as {lo, hi}. A part whose geometry has not arrived yet has none,
// and the planned size stands in for it.
function boxOf(meshes, k) {
    var lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9], any = false;
    (meshes || []).forEach(function (m) {
        var p = m.p || [];
        for (var i = 0; i + 2 < p.length; i += 3) for (var a = 0; a < 3; a++) {
            var v = p[i + a] * (k || 1);
            if (v < lo[a]) lo[a] = v;
            if (v > hi[a]) hi[a] = v;
            any = true;
        }
    });
    return any ? { lo: lo, hi: hi } : null;
}

// Called when a part's geometry file has been read, so labels and streams use the real size from then on.
function setBox(C, i, meshes, k) { C.box[i] = boxOf(meshes, k); }

function plannedBox(p) {
    var sh = p.shape, w = Math.max(sh.r || 0, sh.r0 || 0, (sh.w || 0) / 2), h = (sh.h || 2 * w) / 2, d = Math.max(sh.r || 0, sh.r0 || 0, (sh.d || 0) / 2);
    return { lo: [-w, -h, -d], hi: [w, h, d] };
}

function prepare(scene) {
    var C = { finale: scene.finale || null,  scene: scene, idx: {}, reveal: [], box: [], ev: { spin: [], highlight: [], explode: [], cutaway: [], label: [], flow: [], pulse: [] }, bars: [], pulse: null };
    scene.parts.forEach(function (p, i) { C.idx[p.id] = i; C.reveal.push(undefined); C.box.push(p.shape && p.shape.meshes ? boxOf(p.shape.meshes, p.shape.scale) : null); });
    scene.events.forEach(function (e) {
        if (e.type === "reveal") {
            e.parts.forEach(function (id) { var i = C.idx[id]; if (C.reveal[i] === undefined || e.t0 < C.reveal[i]) C.reveal[i] = e.t0; });
        } else {
            var set = {};
            (e.parts || []).forEach(function (id) { set[C.idx[id]] = true; });
            var copy = {}; for (var k in e) copy[k] = e[k];
            copy.set = set;
            if (e.rates) { copy.rates_i = {}; for (var rid in e.rates) copy.rates_i[C.idx[rid]] = e.rates[rid]; }       // a part with its own rate (degrees a second)
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
    case "glass": a = 0.16; c = c.map(function (x) { return Math.min(255, x * 0.75 + 40); }); metal = 0; rough = 0.08; break;      // clear enough to see what is behind it (both faces are drawn)
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
            var age = Math.min(t, C.finale ? C.finale.t0 : t) - e.t0;      // a demonstration spin stops when the finale begins, so rolling is the only turning left
            var rate = e.rates_i && e.rates_i[i] !== undefined ? e.rates_i[i] : e.rate;
            if (age > 0) s.spin += rate * (age < 1.5 ? age * age / 3 : age - 0.75);
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
        if (fin.rollers) {          // rolling: one turn of the wheel for every circumference travelled; forward along +x is clockwise seen from the side (-z)
            var roll = -(g.d[0] / fin.roll_radius) * 57.2958;
            fin.rollers.forEach(function (id) { parts[C.idx[id]].spin += roll; });
        }
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
            var bx = C.box[i] || plannedBox(p), top = bx.hi[1] + 0.02 * (bx.hi[1] - bx.lo[1]);       // the dot sits on the top of the part as it really is, wherever it has been pulled to
            labels.push({ text: p.label, a: a * Math.min(1, s.k) * outro, at: [p.pos[0] + s.dx + (bx.lo[0] + bx.hi[0]) / 2, p.pos[1] + s.dy + top, p.pos[2] + s.dz + (bx.lo[2] + bx.hi[2]) / 2] });
        });
    });

    var drops = [], streams = [];
    ev.flow.forEach(function (e) {
        var fade = Math.min(ramp((t - e.t0) / 0.6), ramp((e.t1 - t) / 0.6));
        if (fade < 0.02) return;
        var path = scene.paths[e.path], n = 16, size = 0.1, spread = 0.13, a0 = path[0], b0 = path[1];
        if (e.from !== undefined && C.idx[e.from] !== undefined && C.idx[e.to] !== undefined) {
            // a stream runs between the two parts where they are now (pulled apart or not), from the surface of one to the surface of the other, and is drawn
            // small against the smaller of the two
            var ia = C.idx[e.from], ib = C.idx[e.to], pa = scene.parts[ia], pb = scene.parts[ib];
            var ba = C.box[ia] || plannedBox(pa), bb = C.box[ib] || plannedBox(pb), sa = parts[ia], sb = parts[ib];
            var ca = [0, 1, 2].map(function (k) { return pa.pos[k] + [sa.dx, sa.dy, sa.dz][k] + (ba.lo[k] + ba.hi[k]) / 2; });
            var cb = [0, 1, 2].map(function (k) { return pb.pos[k] + [sb.dx, sb.dy, sb.dz][k] + (bb.lo[k] + bb.hi[k]) / 2; });
            var dir = [0, 1, 2].map(function (k) { return cb[k] - ca[k]; }), len = Math.sqrt(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]) || 1;
            dir = dir.map(function (x) { return x / len; });
            var ha = [0, 1, 2].map(function (k) { return (ba.hi[k] - ba.lo[k]) / 2; }), hb = [0, 1, 2].map(function (k) { return (bb.hi[k] - bb.lo[k]) / 2; });
            var ra = exitDistance(ha, dir), rb = exitDistance(hb, dir);
            a0 = [0, 1, 2].map(function (k) { return ca[k] + dir[k] * ra * 0.85; });
            b0 = [0, 1, 2].map(function (k) { return cb[k] - dir[k] * rb * 0.85; });
            var small = Math.min(2 * Math.min(ha[0], ha[1], ha[2]), 2 * Math.min(hb[0], hb[1], hb[2]));
            size = Math.max(0.03, Math.min(0.3, 0.12 * small));
            spread = 0.2 * small;
            streams.push({ from: a0, to: b0, a: e.from, b: e.to, size: size });
        }
        for (var j = 0; j < n; j++) {
            var s = ((t - e.t0) * 0.22 + j / n) % 1;
            drops.push({ x: lerp(a0[0], b0[0], s), y: lerp(a0[1], b0[1], s) + ((j % 5) - 2) * 0.5 * spread, z: lerp(a0[2], b0[2], s) + (((j * 7) % 5) - 2) * 0.5 * spread,
                         s: size / 100 * fade, r: e.color[0] / 255, g: e.color[1] / 255, b: e.color[2] / 255 });
        }
    });

    var rings = [];
    ev.pulse.forEach(function (pu, n) {
        if (C.finale && t >= C.finale.t0) return;            // the ripples stop when the finale begins
        var burst = pu.t1 !== undefined;
        if (!burst && n > 0) return;                         // a signal lesson has one sender
        var si = C.idx[pu.source], src = scene.parts[si], ps = parts[si];
        var life = burst ? 1.6 : WAVE_LIFE, every = burst ? 0.5 : WAVE_EVERY, bx = C.box[si] || plannedBox(src);
        var size = Math.max(bx.hi[0] - bx.lo[0], bx.hi[1] - bx.lo[1], bx.hi[2] - bx.lo[2]);
        var until = burst ? Math.min(t, pu.t1 - life) : t;
        var first = Math.max(0, Math.floor((t - pu.t0 - life) / every)), last = Math.floor((until - pu.t0) / every);
        for (var n2 = first; n2 <= last; n2++) {
            var age = t - pu.t0 - n2 * every;
            if (age < 0 || age > life) continue;
            if (burst)        // small rings around the part itself, where it is now
                rings.push({ x: src.pos[0] + ps.dx, y: src.pos[1] + ps.dy, z: src.pos[2] + ps.dz, radius: size * (0.4 + 1.1 * age / life), a: Math.pow(1 - age / life, 1.3) * 0.8 });
            else
                rings.push({ x: src.pos[0], y: 0.08, z: src.pos[2], radius: 0.3 + WAVE_SPEED * age, a: Math.pow(1 - age / WAVE_LIFE, 1.3) * 0.8 });
        }
    });
    var pu = C.pulse;

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
    return { parts: parts, labels: labels, drops: drops, streams: streams, rings: rings, bars: bars, cam: cam, root: root, fx: fx, env: env };
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

// how far from the centre of a box with these half sizes the ray along `dir` leaves it
function exitDistance(half, dir) {
    var t = 1e9;
    for (var k = 0; k < 3; k++) if (Math.abs(dir[k]) > 1e-6) t = Math.min(t, half[k] / Math.abs(dir[k]));
    return t;
}

// Where a point of the scene appears in the picture, in pixels, for the camera the lesson describes (the orbit camera of Lesson3D.qml: it looks at `target` from `dist` away, turned
// `yaw` about the vertical and raised `pitch`, with a 34 degree vertical field of view). Computed here from the same numbers that move the camera, so a label can never disagree
// with the picture (Qt's own scene-to-screen mapping follows the camera by a frame).
var FOV = 34;
function project(cam, pt, width, height) {
    var yaw = cam.yaw * Math.PI / 180, pitch = -cam.pitch * Math.PI / 180;
    var vx = pt[0] - cam.target[0], vy = pt[1] - cam.target[1], vz = pt[2] - cam.target[2];
    var x1 = vx * Math.cos(yaw) - vz * Math.sin(yaw), z1 = vx * Math.sin(yaw) + vz * Math.cos(yaw);
    var y2 = vy * Math.cos(pitch) + z1 * Math.sin(pitch), z2 = -vy * Math.sin(pitch) + z1 * Math.cos(pitch);
    var depth = cam.dist - z2;
    if (depth <= 0.001) return null;
    var t = Math.tan(FOV * Math.PI / 360), nx = x1 / depth / (t * width / height), ny = y2 / depth / t;
    return { x: (nx * 0.5 + 0.5) * width, y: (0.5 - ny * 0.5) * height, depth: depth };
}

// Labels are a pill above a dot. Where pills would overlap on screen, the later one is lifted until it clears, and its leader line grows to match. Returns, for every label,
// the pill's rectangle {x, y, w, h} in pixels and how far it was lifted. The pill is about 8 pixels per letter plus padding, 28 high, 52 above its dot.
function spreadLabels(labels, cam, width, height) {
    var out = [], placed = [];
    labels.forEach(function (lb) {
        var pt = project(cam, lb.at, width, height);
        if (!pt) { out.push({ x: -1000, y: -1000, w: 0, h: 0, lift: 0 }); return; }
        var w = String(lb.text).length * 8 + 24, h = 28, lift = 0, rect;
        for (var tries = 0; tries < 12; tries++) {
            rect = { x: pt.x - w / 2, y: pt.y - 52 - lift - h / 2, w: w, h: h, lift: lift };
            var clash = placed.some(function (q) { return rect.x < q.x + q.w + 4 && q.x < rect.x + rect.w + 4 && rect.y < q.y + q.h + 4 && q.y < rect.y + rect.h + 4; });
            if (!clash) break;
            lift += h + 4;
        }
        placed.push(rect);
        out.push(rect);
    });
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
