.pragma library

// Procedural meshes for Quick 3D's ProceduralMesh: plain arrays of positions, normals and triangle indexes, built by code. Smooth normals
// where a surface is round (cylinders, pipes, rings, terrain), flat where it has edges (boxes, prisms). Local origin is documented per builder.

function vecs(a) { var o = []; for (var i = 0; i < a.length; i += 3) o.push(Qt.vector3d(a[i], a[i + 1], a[i + 2])); return o; }
function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function norm(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
function mesh() { return { p: [], n: [], i: [] }; }
function vert(m, p, n) { m.p.push(p[0], p[1], p[2]); m.n.push(n[0], n[1], n[2]); return m.p.length / 3 - 1; }
function quad(m, a, b, c, d, n) {
    var i0 = vert(m, a, n), i1 = vert(m, b, n), i2 = vert(m, c, n), i3 = vert(m, d, n);
    m.i.push(i0, i1, i2, i0, i2, i3);
}

// a box centred on x and z, standing on y = oy (bottom face at oy), optionally shifted in x
function box(w, h, d, oy, ox) {
    oy = oy || 0; ox = ox || 0;
    var x = w / 2, z = d / 2, m = mesh();
    var c = function (sx, sy, sz) { return [ox + sx * x, oy + (sy + 1) * h / 2, sz * z]; };
    quad(m, c(-1, -1, 1), c(1, -1, 1), c(1, 1, 1), c(-1, 1, 1), [0, 0, 1]);
    quad(m, c(1, -1, -1), c(-1, -1, -1), c(-1, 1, -1), c(1, 1, -1), [0, 0, -1]);
    quad(m, c(1, -1, 1), c(1, -1, -1), c(1, 1, -1), c(1, 1, 1), [1, 0, 0]);
    quad(m, c(-1, -1, -1), c(-1, -1, 1), c(-1, 1, 1), c(-1, 1, -1), [-1, 0, 0]);
    quad(m, c(-1, 1, 1), c(1, 1, 1), c(1, 1, -1), c(-1, 1, -1), [0, 1, 0]);
    quad(m, c(-1, -1, -1), c(1, -1, -1), c(1, -1, 1), c(-1, -1, 1), [0, -1, 0]);
    return m;
}

// a cylinder on the y axis standing on y = oy, with smooth sides and flat caps
function cyl(r, h, seg, oy) {
    oy = oy || 0;
    var m = mesh(), top = vert(m, [0, oy + h, 0], [0, 1, 0]), bot = vert(m, [0, oy, 0], [0, -1, 0]);
    var ring = [];
    for (var i = 0; i <= seg; i++) {
        var a = i / seg * 2 * Math.PI, c = Math.cos(a), s = Math.sin(a);
        ring.push({ sb: vert(m, [r * c, oy, r * s], [c, 0, s]), st: vert(m, [r * c, oy + h, r * s], [c, 0, s]),
                    cb: vert(m, [r * c, oy, r * s], [0, -1, 0]), ct: vert(m, [r * c, oy + h, r * s], [0, 1, 0]) });
    }
    for (var j = 0; j < seg; j++) {
        var q = ring[j], n = ring[j + 1];
        m.i.push(q.sb, n.sb, n.st, q.sb, n.st, q.st, top, n.ct, q.ct, bot, q.cb, n.cb);
    }
    return m;
}

// a polygon profile [[x, y]...] (counter-clockwise) pushed along z from z0 to z1; flat shaded
function prism(profile, z0, z1) {
    var m = mesh(), n = profile.length;
    for (var i = 0; i < n; i++) {
        var p = profile[i], q = profile[(i + 1) % n], e = norm([q[1] - p[1], -(q[0] - p[0]), 0]);
        quad(m, [p[0], p[1], z0], [q[0], q[1], z0], [q[0], q[1], z1], [p[0], p[1], z1], e);
    }
    var f0 = [], f1 = [];
    for (var j = 0; j < n; j++) { f0.push(vert(m, [profile[j][0], profile[j][1], z0], [0, 0, -1])); f1.push(vert(m, [profile[j][0], profile[j][1], z1], [0, 0, 1])); }
    for (var k = 1; k < n - 1; k++) m.i.push(f0[0], f0[k + 1], f0[k], f1[0], f1[k], f1[k + 1]);
    return m;
}

// a cylinder between two points, smooth sides
function pipe(a, b, r, seg) {
    var axis = norm(sub(b, a)), up = Math.abs(axis[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    var u = norm(cross(axis, up)), w = cross(axis, u), m = mesh(), ring = [];
    var ca = vert(m, a, [-axis[0], -axis[1], -axis[2]]), cb = vert(m, b, axis);
    for (var i = 0; i <= seg; i++) {
        var t = i / seg * 2 * Math.PI, o = [u[0] * Math.cos(t) + w[0] * Math.sin(t), u[1] * Math.cos(t) + w[1] * Math.sin(t), u[2] * Math.cos(t) + w[2] * Math.sin(t)];
        var pa = [a[0] + o[0] * r, a[1] + o[1] * r, a[2] + o[2] * r], pb = [b[0] + o[0] * r, b[1] + o[1] * r, b[2] + o[2] * r];
        ring.push({ sa: vert(m, pa, o), sb: vert(m, pb, o), ea: vert(m, pa, [-axis[0], -axis[1], -axis[2]]), eb: vert(m, pb, axis) });
    }
    for (var j = 0; j < seg; j++) { var q = ring[j], n = ring[j + 1]; m.i.push(q.sa, n.sa, n.sb, q.sa, n.sb, q.sb, ca, n.ea, q.ea, cb, q.eb, n.eb); }
    return m;
}

// a ring (torus) lying flat around the y axis: major radius R, tube radius r
function torus(R, r, segR, segr) {
    var m = mesh(), idx = [];
    for (var i = 0; i <= segR; i++) {
        var u = i / segR * 2 * Math.PI, row = [];
        for (var j = 0; j <= segr; j++) {
            var v = j / segr * 2 * Math.PI, cv = Math.cos(v), sv = Math.sin(v);
            row.push(vert(m, [(R + r * cv) * Math.cos(u), r * sv, (R + r * cv) * Math.sin(u)], [cv * Math.cos(u), sv, cv * Math.sin(u)]));
        }
        idx.push(row);
    }
    for (var a = 0; a < segR; a++) for (var b = 0; b < segr; b++) m.i.push(idx[a][b], idx[a + 1][b], idx[a + 1][b + 1], idx[a][b], idx[a + 1][b + 1], idx[a][b + 1]);
    return m;
}

// a height field over [x0,x1] x [z0,z1] from fn(x, z); smooth normals from finite differences
function terrain(x0, x1, z0, z1, nx, nz, fn) {
    var m = mesh(), e = 0.15, idx = [];
    for (var i = 0; i <= nx; i++) {
        var row = [];
        for (var j = 0; j <= nz; j++) {
            var x = x0 + (x1 - x0) * i / nx, z = z0 + (z1 - z0) * j / nz;
            row.push(vert(m, [x, fn(x, z), z], norm([fn(x - e, z) - fn(x + e, z), 2 * e, fn(x, z - e) - fn(x, z + e)])));
        }
        idx.push(row);
    }
    for (var a = 0; a < nx; a++) for (var b = 0; b < nz; b++) m.i.push(idx[a][b], idx[a][b + 1], idx[a + 1][b + 1], idx[a][b], idx[a + 1][b + 1], idx[a + 1][b]);
    return m;
}

// the sides of a terrain block: vertical walls from the terrain's edge height down to `bottom`, so a landscape reads as a cutaway model
function skirt(x0, x1, z0, z1, nx, nz, fn, bottom) {
    var m = mesh();
    for (var i = 0; i < nx; i++) {
        var xa = x0 + (x1 - x0) * i / nx, xb = x0 + (x1 - x0) * (i + 1) / nx;
        quad(m, [xa, bottom, z0], [xb, bottom, z0], [xb, fn(xb, z0), z0], [xa, fn(xa, z0), z0], [0, 0, -1]);
        quad(m, [xb, bottom, z1], [xa, bottom, z1], [xa, fn(xa, z1), z1], [xb, fn(xb, z1), z1], [0, 0, 1]);
    }
    for (var j = 0; j < nz; j++) {
        var za = z0 + (z1 - z0) * j / nz, zb = z0 + (z1 - z0) * (j + 1) / nz;
        quad(m, [x0, bottom, zb], [x0, bottom, za], [x0, fn(x0, za), za], [x0, fn(x0, zb), zb], [-1, 0, 0]);
        quad(m, [x1, bottom, za], [x1, bottom, zb], [x1, fn(x1, zb), zb], [x1, fn(x1, za), za], [1, 0, 0]);
    }
    quad(m, [x0, bottom, z1], [x1, bottom, z1], [x1, bottom, z0], [x0, bottom, z0], [0, -1, 0]);
    return m;
}

// ---- transforms and compound meshes, for the shape library ----
// o: {pos: [x, y, z], rx, ry, rz (degrees, applied in that order), s: number or [sx, sy, sz]}
function T(m, o) {
    var s = o.s === undefined ? [1, 1, 1] : (typeof o.s === "number" ? [o.s, o.s, o.s] : o.s), d = Math.PI / 180;
    var rx = (o.rx || 0) * d, ry = (o.ry || 0) * d, rz = (o.rz || 0) * d, pos = o.pos || [0, 0, 0], out = { p: [], n: [], i: m.i.slice() };
    function rot(v) {
        var x = v[0], y = v[1], z = v[2], a = y * Math.cos(rx) - z * Math.sin(rx), b = y * Math.sin(rx) + z * Math.cos(rx);
        y = a; z = b;
        a = x * Math.cos(ry) + z * Math.sin(ry); b = -x * Math.sin(ry) + z * Math.cos(ry);
        x = a; z = b;
        a = x * Math.cos(rz) - y * Math.sin(rz); b = x * Math.sin(rz) + y * Math.cos(rz);
        return [a, b, z];
    }
    for (var k = 0; k < m.p.length; k += 3) {
        var p = rot([m.p[k] * s[0], m.p[k + 1] * s[1], m.p[k + 2] * s[2]]), n = rot([m.n[k], m.n[k + 1], m.n[k + 2]]);
        out.p.push(p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]);
        out.n.push(n[0], n[1], n[2]);
    }
    return out;
}

function merge(list) {
    var out = { p: [], n: [], i: [] };
    list.forEach(function (m) {
        var base = out.p.length / 3;
        out.p = out.p.concat(m.p); out.n = out.n.concat(m.n);
        m.i.forEach(function (ix) { out.i.push(ix + base); });
    });
    return out;
}

// a cone or frustum on the y axis from y = oy: radius r0 at the bottom, r1 at the top, smooth sides, flat caps
function frustum(r0, r1, h, seg, oy) {
    oy = oy || 0;
    var m = mesh(), slope = r0 - r1, ring = [], bot = vert(m, [0, oy, 0], [0, -1, 0]), top = vert(m, [0, oy + h, 0], [0, 1, 0]);
    for (var i = 0; i <= seg; i++) {
        var a = i / seg * 2 * Math.PI, c = Math.cos(a), s = Math.sin(a), n = norm([h * c, slope, h * s]);
        ring.push({ sb: vert(m, [r0 * c, oy, r0 * s], n), st: vert(m, [r1 * c, oy + h, r1 * s], n),
                    cb: vert(m, [r0 * c, oy, r0 * s], [0, -1, 0]), ct: vert(m, [r1 * c, oy + h, r1 * s], [0, 1, 0]) });
    }
    for (var j = 0; j < seg; j++) { var q = ring[j], n2 = ring[j + 1]; m.i.push(q.sb, n2.sb, n2.st, q.sb, n2.st, q.st, bot, q.cb, n2.cb, top, n2.ct, q.ct); }
    return m;
}

// a sphere, or its upper cap when `cap` < pi (a dome): radius r around the origin
function sphere(r, segU, segV, cap) {
    cap = cap === undefined ? Math.PI : cap;
    var m = mesh(), idx = [];
    for (var j = 0; j <= segV; j++) {
        var th = j / segV * cap, row = [];
        for (var i = 0; i <= segU; i++) {
            var a = i / segU * 2 * Math.PI, nx = Math.sin(th) * Math.cos(a), ny = Math.cos(th), nz = Math.sin(th) * Math.sin(a);
            row.push(vert(m, [r * nx, r * ny, r * nz], [nx, ny, nz]));
        }
        idx.push(row);
    }
    for (var b = 0; b < segV; b++) for (var u = 0; u < segU; u++) m.i.push(idx[b][u], idx[b + 1][u], idx[b + 1][u + 1], idx[b][u], idx[b + 1][u + 1], idx[b][u + 1]);
    return m;
}

// an open tube on the y axis (no caps), centred on y = 0
function tube(r, h, seg) {
    var m = mesh();
    for (var i = 0; i < seg; i++) {
        var a0 = i / seg * 2 * Math.PI, a1 = (i + 1) / seg * 2 * Math.PI, c0 = Math.cos(a0), s0 = Math.sin(a0), c1 = Math.cos(a1), s1 = Math.sin(a1);
        var q = [vert(m, [r * c0, -h / 2, r * s0], [c0, 0, s0]), vert(m, [r * c1, -h / 2, r * s1], [c1, 0, s1]), vert(m, [r * c1, h / 2, r * s1], [c1, 0, s1]), vert(m, [r * c0, h / 2, r * s0], [c0, 0, s0])];
        m.i.push(q[0], q[1], q[2], q[0], q[2], q[3]);
    }
    return m;
}

// ---- free-form shapes from plain numbers (custom parts) ----
// Both are double-sided: a model-written profile or outline may be wound either way, and the right side still lights correctly.

// one triangle, drawn from both sides; a, b, c are [x, y, z], na/nb/nc their outward normals
function dbl(m, a, b, c, na, nb, nc) {
    var g = cross(sub(b, a), sub(c, a)), avg = [na[0] + nb[0] + nc[0], na[1] + nb[1] + nc[1], na[2] + nb[2] + nc[2]];
    var front = g[0] * avg[0] + g[1] * avg[1] + g[2] * avg[2] >= 0;
    var i0 = vert(m, a, na), i1 = vert(m, b, nb), i2 = vert(m, c, nc);
    var j0 = vert(m, a, [-na[0], -na[1], -na[2]]), j1 = vert(m, b, [-nb[0], -nb[1], -nb[2]]), j2 = vert(m, c, [-nc[0], -nc[1], -nc[2]]);
    if (front) { m.i.push(i0, i1, i2, j0, j2, j1); } else { m.i.push(i0, i2, i1, j0, j1, j2); }
}

// a profile [[radius, height], ...] revolved around the y axis; sharp corners stay sharp, gentle bends are smoothed
function lathe(profile, seg) {
    var m = mesh(), n = profile.length, norms = [];
    for (var i = 0; i < n - 1; i++) {
        var dr = profile[i + 1][0] - profile[i][0], dy = profile[i + 1][1] - profile[i][1], l = Math.hypot(dr, dy) || 1;
        norms.push([dy / l, -dr / l]);
    }
    function at(i, k) {       // the normal at profile point i for segment k: blended with the neighbouring segment when the bend is gentle
        var own = norms[k], other = norms[i === k ? k - 1 : k + 1];
        if (!other || own[0] * other[0] + own[1] * other[1] < 0.77) return own;
        var x = own[0] + other[0], y = own[1] + other[1], q = Math.hypot(x, y) || 1;
        return [x / q, y / q];
    }
    for (var s = 0; s < n - 1; s++) {
        for (var j = 0; j < seg; j++) {
            var a0 = j / seg * 2 * Math.PI, a1 = (j + 1) / seg * 2 * Math.PI;
            function pt(i, a) { return [profile[i][0] * Math.cos(a), profile[i][1], profile[i][0] * Math.sin(a)]; }
            function nm(i, a) { var q = at(i, s); return [q[0] * Math.cos(a), q[1], q[0] * Math.sin(a)]; }
            var A = pt(s, a0), B = pt(s, a1), C = pt(s + 1, a1), D = pt(s + 1, a0);
            var nA = nm(s, a0), nB = nm(s, a1), nC = nm(s + 1, a1), nD = nm(s + 1, a0);
            dbl(m, A, B, C, nA, nB, nC);
            dbl(m, A, C, D, nA, nC, nD);
        }
    }
    return m;
}

// triangles that fill a flat polygon [[x, z], ...] (ear clipping; falls back to a fan for a degenerate outline)
function triangulate(poly) {
    var idx = poly.map(function (_, i) { return i; }), out = [], area = 0;
    for (var i = 0; i < poly.length; i++) { var p = poly[i], q = poly[(i + 1) % poly.length]; area += p[0] * q[1] - q[0] * p[1]; }
    var sign = area >= 0 ? 1 : -1, guard = 0;
    function cr(a, b, c) { return ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * sign; }
    function inside(p, a, b, c) { return cr(a, b, p) >= 0 && cr(b, c, p) >= 0 && cr(c, a, p) >= 0; }
    while (idx.length > 3 && guard++ < 500) {
        var clipped = false;
        for (var k = 0; k < idx.length; k++) {
            var ia = idx[(k + idx.length - 1) % idx.length], ib = idx[k], ic = idx[(k + 1) % idx.length];
            var A = poly[ia], B = poly[ib], C = poly[ic];
            if (cr(A, B, C) <= 1e-9) continue;
            var ear = true;
            for (var t = 0; t < idx.length && ear; t++) {
                var it = idx[t];
                if (it !== ia && it !== ib && it !== ic && inside(poly[it], A, B, C)) ear = false;
            }
            if (!ear) continue;
            out.push([ia, ib, ic]); idx.splice(k, 1); clipped = true; break;
        }
        if (!clipped) break;
    }
    if (idx.length === 3) out.push([idx[0], idx[1], idx[2]]);
    else for (var f = 1; f + 1 < idx.length; f++) out.push([idx[0], idx[f], idx[f + 1]]);
    return out;
}

// an outline [[x, z], ...] standing on the xz plane, pushed up by h and centred on y = 0
function extrude(outline, h) {
    var m = mesh(), n = outline.length, y0 = -h / 2, y1 = h / 2;
    for (var i = 0; i < n; i++) {
        var p = outline[i], q = outline[(i + 1) % n], dx = q[0] - p[0], dz = q[1] - p[1], l = Math.hypot(dx, dz) || 1, nn = [dz / l, 0, -dx / l];
        dbl(m, [p[0], y0, p[1]], [q[0], y0, q[1]], [q[0], y1, q[1]], nn, nn, nn);
        dbl(m, [p[0], y0, p[1]], [q[0], y1, q[1]], [p[0], y1, p[1]], nn, nn, nn);
    }
    triangulate(outline).forEach(function (t) {
        var a = outline[t[0]], b = outline[t[1]], c = outline[t[2]];
        dbl(m, [a[0], y1, a[1]], [b[0], y1, b[1]], [c[0], y1, c[1]], [0, 1, 0], [0, 1, 0], [0, 1, 0]);
        dbl(m, [a[0], y0, a[1]], [b[0], y0, b[1]], [c[0], y0, c[1]], [0, -1, 0], [0, -1, 0], [0, -1, 0]);
    });
    return m;
}
