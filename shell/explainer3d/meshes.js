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
