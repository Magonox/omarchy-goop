.pragma library

// The liquid rim of a goop. Points around a circle whose radius is nudged by a few slow standing waves, plus a "slosh" bump that
// travels around the rim and a slightly heavier bottom, then joined with a smooth closed curve. Each goop's seed gives it its own phases.
var N = 12;

function wrap(a) {
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a < -Math.PI) a += 2 * Math.PI;
    return a;
}

// energy 0..1: how agitated the goop is (speaking, thinking, startled). It wobbles bigger and faster.
function points(cx, cy, R, t, seed, squish, energy) {
    var e = energy || 0;
    var p2 = (seed % 89) * 0.071, p3 = (seed % 53) * 0.119, p4 = (seed % 37) * 0.17, ps = (seed % 71) * 0.089;
    var sp = 1 + e * 0.9;
    var k = 1 + e * 1.3;
    var a2 = 0.11 * k, a3 = 0.085 * k, a4 = 0.045 * k, ab = 0.16 * (1 + e * 0.8);
    var psi = ps * 6.28 + t * 0.55 * sp;
    var out = [];
    for (var i = 0; i < N; i++) {
        var th = i / N * 2 * Math.PI;
        var d = wrap(th - psi);
        var r = 1
            + a2 * Math.sin(2 * th + t * 1.15 * sp + p2 * 6.28)
            + a3 * Math.sin(3 * th - t * 1.45 * sp + p3 * 6.28)
            + a4 * Math.sin(4 * th + t * 1.9 * sp + p4 * 6.28)
            + ab * Math.exp(-d * d / 0.6)
            + 0.06 * Math.sin(th);
        out.push({ x: cx + R * r * Math.cos(th) * (1 + squish), y: cy + R * r * Math.sin(th) * (1 - squish) });
    }
    return out;
}

function f(v) { return Math.round(v * 100) / 100; }

// Closed Catmull-Rom curve through the points, as SVG path text (for QtQuick.Shapes PathSvg).
function svg(pts) {
    var n = pts.length, d = "M " + f(pts[0].x) + " " + f(pts[0].y);
    for (var i = 0; i < n; i++) {
        var p0 = pts[(i + n - 1) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
        d += " C " + f(p1.x + (p2.x - p0.x) / 6) + " " + f(p1.y + (p2.y - p0.y) / 6)
           + " " + f(p2.x - (p3.x - p1.x) / 6) + " " + f(p2.y - (p3.y - p1.y) / 6)
           + " " + f(p2.x) + " " + f(p2.y);
    }
    return d + " Z";
}

// The same curve on a 2D canvas context (the peel animation).
function draw(c, pts) {
    var n = pts.length;
    c.beginPath();
    c.moveTo(pts[0].x, pts[0].y);
    for (var i = 0; i < n; i++) {
        var p0 = pts[(i + n - 1) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
        c.bezierCurveTo(p1.x + (p2.x - p0.x) / 6, p1.y + (p2.y - p0.y) / 6, p2.x - (p3.x - p1.x) / 6, p2.y - (p3.y - p1.y) / 6, p2.x, p2.y);
    }
    c.closePath();
}
