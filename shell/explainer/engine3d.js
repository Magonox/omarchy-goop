.pragma library

// A tiny 3D renderer in plain JavaScript for a 2D canvas: meshes built from math, perspective camera, back-face culling, flat shading,
// painter's algorithm (objects sorted far to near, translucent ones last), labels and billboard particles. No assets, no GPU APIs.
// World: x right, y up, z toward the viewer. Scenes are tens of shapes, so this is cheap.

function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
var LIGHT = norm([-0.45, 0.85, 0.6]);
var widths = {};

// ---- meshes: {v: [[x,y,z]...], f: [[vertex indices]...]}; normals are oriented outward at render time, so winding does not matter ----
function box(w, h, d, ox, oy, oz) {
    ox = ox || 0; oy = oy || 0; oz = oz || 0;
    var x = w / 2, y = h / 2, z = d / 2, v = [];
    [-1, 1].forEach(function (sx) { [-1, 1].forEach(function (sy) { [-1, 1].forEach(function (sz) { v.push([ox + sx * x, oy + sy * y, oz + sz * z]); }); }); });
    return { v: v, f: [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]] };
}

function cylinder(r, h, seg) {       // axis along y, centred on the origin
    var v = [], f = [], top = [], bot = [];
    for (var i = 0; i < seg; i++) {
        var a = i / seg * 2 * Math.PI, x = r * Math.cos(a), z = r * Math.sin(a);
        v.push([x, -h / 2, z]); v.push([x, h / 2, z]);
    }
    for (var j = 0; j < seg; j++) {
        var n = (j + 1) % seg;
        f.push([2 * j, 2 * n, 2 * n + 1, 2 * j + 1]);
        top.push(2 * j + 1); bot.push(2 * j);
    }
    f.push(top); f.push(bot);
    return { v: v, f: f };
}

function prism(profile, z0, z1) {     // a 2D profile [[x,y]...] pushed along z
    var v = [], f = [], n = profile.length, a = [], b = [];
    profile.forEach(function (p) { v.push([p[0], p[1], z0]); });
    profile.forEach(function (p) { v.push([p[0], p[1], z1]); });
    for (var i = 0; i < n; i++) { var k = (i + 1) % n; f.push([i, k, n + k, n + i]); a.push(i); b.push(n + i); }
    f.push(a); f.push(b);
    return { v: v, f: f };
}

function pipe(p, q, r, seg) {         // a cylinder between two points
    var axis = norm(sub(q, p)), up = Math.abs(axis[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    var u = norm(cross(axis, up)), w = cross(axis, u), v = [], f = [], c0 = [], c1 = [];
    for (var i = 0; i < seg; i++) {
        var a = i / seg * 2 * Math.PI, o = [u[0] * Math.cos(a) + w[0] * Math.sin(a), u[1] * Math.cos(a) + w[1] * Math.sin(a), u[2] * Math.cos(a) + w[2] * Math.sin(a)];
        v.push([p[0] + o[0] * r, p[1] + o[1] * r, p[2] + o[2] * r]);
        v.push([q[0] + o[0] * r, q[1] + o[1] * r, q[2] + o[2] * r]);
    }
    for (var j = 0; j < seg; j++) { var n = (j + 1) % seg; f.push([2 * j, 2 * n, 2 * n + 1, 2 * j + 1]); c0.push(2 * j); c1.push(2 * j + 1); }
    f.push(c0); f.push(c1);
    return { v: v, f: f };
}

function world(mesh, pos, rotY) {
    var c = Math.cos(rotY || 0), s = Math.sin(rotY || 0);
    return mesh.v.map(function (p) { return [pos[0] + c * p[0] + s * p[2], pos[1] + p[1], pos[2] - s * p[0] + c * p[2]]; });
}

function rgba(c, shade, a) {
    return "rgba(" + Math.min(255, Math.round(c[0] * shade)) + "," + Math.min(255, Math.round(c[1] * shade)) + "," + Math.min(255, Math.round(c[2] * shade)) + "," + a + ")";
}

// scene: {cam: {target, yaw, pitch, dist, f}, objects: [{mesh, pos, rotY, color, alpha, glow}], particles: [{p, r, color, alpha}], labels: [{text, at, dx, dy, alpha}]}
function render(ctx, W, H, scene) {
    var cam = scene.cam, cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    function view(p) {
        var x = p[0] - cam.target[0], y = p[1] - cam.target[1], z = p[2] - cam.target[2];
        var x1 = cy * x + sy * z, z1 = -sy * x + cy * z;
        return [x1, cp * y - sp * z1, sp * y + cp * z1 - cam.dist];
    }
    function proj(v) { var k = cam.f / -v[2]; return [W / 2 + v[0] * k, H / 2 - v[1] * k, k]; }

    var items = [];
    scene.objects.forEach(function (o) {
        if (!(o.alpha > 0.01)) return;
        var wv = world(o.mesh, o.pos, o.rotY), vv = wv.map(view), oc = [0, 0, 0], ov = [0, 0, 0];
        wv.forEach(function (p) { oc[0] += p[0]; oc[1] += p[1]; oc[2] += p[2]; });
        oc = [oc[0] / wv.length, oc[1] / wv.length, oc[2] / wv.length];
        var faces = [];
        o.mesh.f.forEach(function (fi) {
            var w0 = wv[fi[0]], w1 = wv[fi[1]], w2 = wv[fi[2]], n = norm(cross(sub(w1, w0), sub(w2, w0)));
            var c = [0, 0, 0], vz = 0, near = false;
            fi.forEach(function (i) { c[0] += wv[i][0]; c[1] += wv[i][1]; c[2] += wv[i][2]; vz += vv[i][2]; if (vv[i][2] > -0.5) near = true; });
            c = [c[0] / fi.length, c[1] / fi.length, c[2] / fi.length];
            var flip = dot(n, sub(c, oc)) < 0;
            if (flip) n = [-n[0], -n[1], -n[2]];
            var v0 = vv[fi[0]], v1 = vv[fi[1]], v2 = vv[fi[2]], nv = cross(sub(v1, v0), sub(v2, v0));
            if (flip) nv = [-nv[0], -nv[1], -nv[2]];
            var cv = [(v0[0] + v1[0] + v2[0]) / 3, (v0[1] + v1[1] + v2[1]) / 3, (v0[2] + v1[2] + v2[2]) / 3];
            if (near || dot(nv, [-cv[0], -cv[1], -cv[2]]) <= 0) return;      // behind the camera, or facing away
            faces.push({ z: vz / fi.length, pts: fi.map(function (i) { return proj(vv[i]); }), shade: 0.45 + 0.55 * Math.max(0, dot(n, LIGHT)) });
        });
        faces.sort(function (a, b) { return a.z - b.z; });
        var cvz = view(oc)[2];
        items.push({ o: o, faces: faces, z: cvz, translucent: o.alpha < 0.97, layer: o.layer || 1 });
    });
    // layers first (0 = ground, 1 = solids, 2 = see-through volumes), then translucent after opaque, then far to near
    items.sort(function (a, b) { return (a.layer - b.layer) || (a.translucent - b.translucent) || (a.z - b.z); });

    items.forEach(function (it) {
        var o = it.o;
        it.faces.forEach(function (fc) {
            ctx.beginPath();
            ctx.moveTo(fc.pts[0][0], fc.pts[0][1]);
            for (var i = 1; i < fc.pts.length; i++) ctx.lineTo(fc.pts[i][0], fc.pts[i][1]);
            ctx.closePath();
            ctx.fillStyle = rgba(o.color, fc.shade, o.alpha);
            ctx.fill();
            ctx.lineWidth = o.glow > 0 ? 1.6 : 0.8;
            ctx.strokeStyle = o.glow > 0 ? "rgba(255,255,255," + (0.35 + 0.6 * o.glow) * o.alpha + ")" : "rgba(10,14,22," + 0.4 * o.alpha + ")";
            ctx.stroke();
        });
    });

    (scene.particles || []).forEach(function (q) {
        if (!(q.alpha > 0.01)) return;
        var p = proj(view(q.p)), r = Math.max(1.2, q.r * p[2]);
        ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 2 * Math.PI);
        ctx.fillStyle = rgba(q.color, 1, q.alpha); ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255," + 0.5 * q.alpha + ")"; ctx.lineWidth = 0.7; ctx.stroke();
    });

    (scene.labels || []).forEach(function (l) {
        if (!(l.alpha > 0.02)) return;
        var p = proj(view(l.at)), x = p[0] + (l.dx || 0), y = p[1] + (l.dy || -34);
        ctx.font = "600 14px sans-serif";
        var w = widths[l.text] || (widths[l.text] = ctx.measureText(l.text).width + 18);
        ctx.globalAlpha = l.alpha;
        ctx.strokeStyle = "rgba(255,255,255,0.7)"; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(x, y + 12); ctx.stroke();
        ctx.beginPath(); ctx.arc(p[0], p[1], 3, 0, 2 * Math.PI); ctx.fillStyle = "white"; ctx.fill();
        ctx.fillStyle = "rgba(16,18,26,0.88)";
        ctx.beginPath();
        ctx.moveTo(x - w / 2 + 9, y - 10); ctx.lineTo(x + w / 2 - 9, y - 10); ctx.arc(x + w / 2 - 9, y + 2, 12, -Math.PI / 2, Math.PI / 2);
        ctx.lineTo(x - w / 2 + 9, y + 14); ctx.arc(x - w / 2 + 9, y + 2, 12, Math.PI / 2, 3 * Math.PI / 2); ctx.fill();
        ctx.fillStyle = "white"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(l.text, x, y + 2);
        ctx.globalAlpha = 1;
    });
}
