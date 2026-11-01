.pragma library
.import "meshes.js" as M

// The shape library: turns a part's `shape` description into one or more meshes, each with a material role (main, accent, dark, glass, glow,
// screen, led, floor). Every shape is centred on the origin; axial shapes stand on the y axis (the layout lays them on their side).

function blades(r, count, thick, chord, pitch) {
    var list = [], len = r * 0.7;
    for (var k = 0; k < count; k++) {
        var b = M.box(len, thick, chord, 0, r * 0.3 + len / 2);
        list.push(M.T(b, { rx: pitch, ry: k * 360 / count }));
    }
    return M.merge(list);
}

function build(sh) {
    var t = sh.type, r = sh.r || 0.5, h = sh.h || 1;
    switch (t) {
    case "fan":
        return [{ role: "accent", mesh: M.cyl(r * 0.3, h, 20, -h / 2) },
                { role: "blade", mesh: M.T(blades(r, sh.blades || 12, 0.045, r * 0.2, 24), { pos: [0, 0, 0] }) },
                { role: "dark", mesh: M.T(M.torus(r * 0.99, r * 0.03, 40, 8), { pos: [0, 0, 0] }) }];
    case "stages": {
        var subs = [{ role: "glass", mesh: M.frustum(sh.r0, sh.r1, h, 32, -h / 2) }], n = sh.n || 3;
        for (var i = 0; i < n; i++) {
            var y = -h / 2 + h * (i + 0.5) / n, ri = (sh.r0 + (sh.r1 - sh.r0) * (i + 0.5) / n) * 0.9;
            subs.push({ role: "accent", mesh: M.cyl(ri * 0.26, h / n * 0.5, 14, y - h / n * 0.25) });
            subs.push({ role: "blade", mesh: M.T(blades(ri, sh.blades || 10, 0.035, ri * 0.18, 22), { pos: [0, y, 0], ry: i * 17 }) });
        }
        return subs;
    }
    case "chamber":
        return [{ role: "glass", mesh: M.cyl(r, h, 32, -h / 2) },
                { role: "glow", mesh: M.frustum(r * 0.62, r * 0.2, h * 0.8, 24, -h * 0.4) },
                { role: "main", mesh: M.merge([0.2, 0.5, 0.8].map(function (f) { return M.T(M.torus(r, r * 0.028, 36, 8), { pos: [0, -h / 2 + h * f, 0] }); })) }];
    case "nozzle":
        return [{ role: "main", mesh: M.frustum(sh.r0, sh.r1, h, 32, -h / 2) },
                { role: "accent", mesh: M.T(M.torus(sh.r1, sh.r1 * 0.07, 32, 8), { pos: [0, h / 2, 0] }) },
                { role: "glow", mesh: M.frustum(sh.r1 * 0.88, 0.04, h * 1.0, 20, h / 2) }];
    case "casing":
        return [{ role: "main", mesh: M.tube(r, h, 48) }];
    case "shaft":
        return [{ role: "main", mesh: M.cyl(r, h, 14, -h / 2) }];
    case "router": {
        return [{ role: "main", mesh: M.box(0.8, 0.14, 0.5, -h / 2) },
                { role: "dark", mesh: M.merge([-0.3, 0.3].map(function (x) { return M.T(M.cyl(0.028, 0.46, 8, 0), { pos: [x, -h / 2 + 0.14, -0.15], rz: x < 0 ? 12 : -12 }); })) },
                { role: "led", mesh: M.merge([-0.2, -0.08, 0.04].map(function (x) { return M.box(0.06, 0.03, 0.04, -h / 2 + 0.14, x); })) }];
    }
    case "tower":
        return tower(sh);
    case "mesh":
        return meshSubs(sh.meshes || [], sh.scale);
    case "device":
        return device(sh);
    case "wall":
        return [{ role: "main", mesh: M.box(sh.w, h, sh.t, -h / 2) }];
    case "floor":
        return [{ role: "floor", mesh: M.box(sh.w, h, sh.d, -h / 2) }];
    case "capsule":
        return [{ role: "main", mesh: M.frustum(r, r * 0.42, h * 0.82, 40, -h / 2) },
                { role: "main", mesh: M.T(M.sphere(r * 0.42, 24, 8, Math.PI / 2), { pos: [0, -h / 2 + h * 0.82, 0] }) },
                { role: "accent", mesh: M.T(M.torus(r * 0.99, r * 0.05, 40, 8), { pos: [0, -h / 2 + 0.03, 0] }) },
                { role: "screen", mesh: M.T(M.sphere(r * 0.17, 14, 8), { pos: [0, -h * 0.05, r * 0.72], s: [1, 1, 0.5] }) }];
    case "module":
        return [{ role: "glass", mesh: M.cyl(r, h, 40, -h / 2) },
                { role: "accent", mesh: M.merge([-0.34, 0.34].map(function (f) { return M.T(M.torus(r, r * 0.05, 40, 8), { pos: [0, h * f, 0] }); })) },
                { role: "dark", mesh: M.merge([0, 90, 180, 270].map(function (a) { return M.T(M.box(0.12, h * 0.8, 0.08, -h * 0.4, r), { ry: a }); })) }];
    case "tank":
        return [{ role: "main", mesh: M.merge([M.cyl(r, h * 0.62, 28, -h * 0.31),
                                               M.T(M.sphere(r, 28, 8, Math.PI / 2), { pos: [0, h * 0.31, 0] }),
                                               M.T(M.sphere(r, 28, 8, Math.PI / 2), { pos: [0, -h * 0.31, 0], rx: 180 })]) },
                { role: "accent", mesh: M.T(M.torus(r * 1.0, r * 0.045, 32, 8), { pos: [0, 0, 0] }) }];
    case "engine":
        return [{ role: "main", mesh: M.frustum(r, r * 0.3, h, 36, -h / 2) },
                { role: "accent", mesh: M.T(M.torus(r * 0.98, r * 0.06, 36, 8), { pos: [0, -h / 2, 0] }) },
                { role: "dark", mesh: M.cyl(r * 0.34, h * 0.35, 14, h / 2) },
                { role: "glow", mesh: M.frustum(0.04, r * 0.8, h * 1.2, 20, -h / 2 - h * 1.2) }];
    case "panel":
        return [{ role: "main", mesh: M.box(sh.w, 0.05, sh.d, -0.025) },
                { role: "dark", mesh: M.box(sh.w + 0.1, 0.03, sh.d + 0.1, -0.06) },
                { role: "accent", mesh: M.merge([-0.4, -0.2, 0, 0.2, 0.4].map(function (f) { return M.box(0.03, 0.012, sh.d, 0.0, sh.w * f); })) }];
    case "dish":
        return [{ role: "main", mesh: M.T(M.sphere(r, 30, 8, Math.PI / 2.4), { pos: [0, 0.1, 0], rx: 180, s: [1, 0.45, 1] }) },
                { role: "dark", mesh: M.cyl(0.05, r * 0.75, 10, 0) },
                { role: "accent", mesh: M.cyl(0.05, 0.28, 10, 0.2) }];
    case "thruster":
        return [{ role: "dark", mesh: M.T(M.frustum(r, r * 0.45, h, 14, -h / 2), { rz: -90 }) },
                { role: "accent", mesh: M.T(M.torus(r, r * 0.12, 14, 6), { rz: -90, pos: [-h / 2, 0, 0] }) }];
    case "box": return [{ role: "main", mesh: M.box(sh.w, h, sh.d, -h / 2) }];
    case "cylinder": return [{ role: "main", mesh: M.cyl(r, h, 28, -h / 2) }];
    case "sphere": return [{ role: "main", mesh: M.sphere(r, 28, 16) }];
    case "cone": return [{ role: "main", mesh: M.frustum(r, 0.02, h, 28, -h / 2) }];
    }
    return [{ role: "main", mesh: M.box(1, 1, 1, -0.5) }];
}

// a code part's meshes (from the scene file, or from its own file as it arrives) -> the sub-meshes the renderer draws
function meshSubs(meshes, scale) {
    return meshes.map(function (m) { return { role: roleOf(m.look, m.material), mesh: M.T({ p: m.p, n: m.n, i: m.i }, { s: scale || 1 }) }; });
}

function roleOf(look, name) {
    return look === "glass" ? "g:" + name : look === "glow" ? "w:" + name : look === "screen" ? "screen" : look === "led" ? "led" : "m:" + name;
}

function tower(sh) {
    var h = sh.h, y0 = -h / 2, tilt = 6.4, legs = [], rings = [];
    [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(function (s) {
        legs.push(M.T(M.cyl(0.03, h, 6, -h / 2), { pos: [s[0] * 0.2, 0, s[1] * 0.2], rz: s[0] * tilt, rx: -s[1] * tilt }));
    });
    [0.08, 0.3, 0.52, 0.74].forEach(function (f) {
        var off = 0.333 - 0.111 * (f * h);
        rings.push(M.T(M.torus(Math.SQRT2 * off, 0.012, 20, 6), { pos: [0, y0 + f * h, 0] }));
    });
    return [{ role: "main", mesh: M.merge(legs) },
            { role: "dark", mesh: M.merge(rings) },
            { role: "accent", mesh: M.merge([M.T(M.cyl(0.02, h * 0.2, 6, 0), { pos: [0, h / 2, 0] }),
                                               M.T(M.box(0.34, 0.05, 0.05, 0), { pos: [0, y0 + h * 0.86, 0] }),
                                               M.T(M.box(0.05, 0.05, 0.34, 0), { pos: [0, y0 + h * 0.8, 0] })]) },
            { role: "led", mesh: M.T(M.sphere(0.07, 12, 8), { pos: [0, h / 2 + h * 0.2, 0] }) }];
}

function device(sh) {
    var v = sh.variant, h = sh.h || 0.6, y0 = -h / 2;
    if (v === "antenna") {                                  // a rooftop TV antenna: a mast, a boom, and rods that get shorter toward the front
        var rods = [0.78, 0.7, 0.58, 0.5, 0.44, 0.4].map(function (len, i) {
            return M.T(M.box(len, 0.025, 0.025, -0.0125), { pos: [0, y0 + 0.44, -0.3 + i * 0.12] });
        });
        return [{ role: "dark", mesh: M.cyl(0.03, 0.44, 8, y0) },
                { role: "dark", mesh: M.T(M.box(0.03, 0.03, 0.8, -0.015), { pos: [0, y0 + 0.44, 0] }) },
                { role: "main", mesh: M.merge(rods) }];
    }
    if (v === "phone")
        return [{ role: "dark", mesh: M.box(0.3, 0.05, 0.54, y0 + 0.2) },
                { role: "screen", mesh: M.box(0.26, 0.012, 0.48, y0 + 0.245) }];
    if (v === "tv")
        return [{ role: "dark", mesh: M.merge([M.box(1.5, 0.9, 0.08, y0 + 0.26), M.box(0.5, 0.26, 0.28, y0)]) },
                { role: "screen", mesh: M.T(M.box(1.4, 0.8, 0.02, 0), { pos: [0, y0 + 0.71, 0.045] }) }];
    if (v === "speaker")
        return [{ role: "dark", mesh: M.cyl(0.3, 0.55, 20, y0) }, { role: "screen", mesh: M.cyl(0.31, 0.04, 20, y0 + 0.4) }];
    return [{ role: "dark", mesh: M.box(0.78, 0.05, 0.54, y0) },                                          // laptop: base, then the lid standing open
            { role: "dark", mesh: M.T(M.box(0.78, 0.5, 0.035, 0), { pos: [0, y0 + 0.3, -0.25], rx: -12 }) },
            { role: "screen", mesh: M.T(M.box(0.7, 0.42, 0.01, 0), { pos: [0, y0 + 0.3, -0.225], rx: -12 }) }];
}
