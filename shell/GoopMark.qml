import QtQuick
import "goo.js" as Goo

// The Goop mascot, built from the very parts the goops on your windows are made of: the wobbling liquid body (GooBody / goo.js) and the drip that forms on a thin neck,
// lets go and falls (Drip). Scaled up from the real goop (radius 13) to `size` (its width), so it moves exactly like the real thing. Used in the setup card and the marketing art.
Item {
    id: g
    property color color: "#e5484d"
    property real size: 44
    property bool animate: true
    property real phase: 0                        // offsets the wobble so several marks do not move together
    property real energy: 0.55                    // how lively the liquid is (0 calm, 1 very agitated)
    readonly property real k: size / 26           // the real goop's radius is 13
    width: size; height: size * 1.6               // room underneath for the drip
    property real t: phase
    property real blink: 1
    property real glance: 0
    // The wet gloss rides on the body: it sits 60% of the way from the centre to the upper-left point of the live outline (the same points GooBody draws), so it moves,
    // squashes and shrinks with the liquid and can never be left floating where the body no longer is. The drip hangs from the live bottom of the outline for the same reason.
    readonly property var rim: Goo.points(13, 13, 13, t, 7, 0.04, energy)
    readonly property real glossX: 13 + 0.52 * (rim[8].x - 13)
    readonly property real glossY: 13 + 0.52 * (rim[8].y - 13)
    readonly property real glossK: Math.max(0.45, Math.min(1.0, Math.hypot(rim[8].x - 13, rim[8].y - 13) / 13))

    readonly property double t0: Date.now()
    Timer { interval: 33; repeat: true; running: g.animate && g.visible; onTriggered: { g.t = (Date.now() - g.t0) / 1000 + g.phase; g.glance = Math.sin(g.t * 0.8) * 1.6; } }
    Timer { interval: 3400; repeat: true; running: g.animate && g.visible; onTriggered: blinkAnim.start() }
    Timer { interval: 4200; repeat: true; running: g.animate && g.visible; triggeredOnStart: true; onTriggered: drip.trigger() }       // a drip every few seconds, so it reads as goo at a glance
    SequentialAnimation { id: blinkAnim; NumberAnimation { target: g; property: "blink"; to: 0.1; duration: 90 } NumberAnimation { target: g; property: "blink"; to: 1; duration: 150 } }

    Item {
        width: 26; height: 42
        transformOrigin: Item.TopLeft
        scale: g.k
        GooBody { r: 13; color: g.color; seed: 7; t: g.t; energy: g.energy; squish: 0.04 }
        Rectangle { x: g.glossX - 4; y: g.glossY - 1.8; width: 8; height: 3.6; radius: 1.8; rotation: -24; scale: g.glossK; color: "white"; opacity: 0.3 }      // a wet gloss, like a drop of paint, riding on the body
        Item {      // the eyes glance left and right together, and blink
            x: g.glance; y: 0
            Rectangle { x: 7.6; y: 9.2 + (1 - g.blink) * 3; width: 3.4; height: 7 * g.blink + 0.7; radius: 1.7; color: "white" }
            Rectangle { x: 15.0; y: 9.2 + (1 - g.blink) * 3; width: 3.4; height: 7 * g.blink + 0.7; radius: 1.7; color: "white" }
        }
        Drip { id: drip; x: g.rim[3].x; y: g.rim[3].y - 0.8; color: g.color; calm: 100 }              // hangs from the bottom of the live outline (point 3 is straight down); calm is high so only the timer above starts drips
    }
}
