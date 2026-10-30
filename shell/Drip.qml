import QtQuick
import QtQuick.Shapes

// A drip: a bulge forms at the bottom of the goop, stretches on a thin neck, lets go, falls a few pixels and fades.
// The origin (0, 0) is the bottom of the goop. Only created at the "full" animation level.
Item {
    id: drip
    property color color: "#e5484d"
    property real calm: 1               // above 1 = drips less often (speaking), below 1 = more often (thinking)
    property real dx: 0                 // where along the bottom this drip forms
    property real neck: 0               // length of the neck; 0 = no drip
    property real bulb: 0               // radius of the drop at its end
    property real half: 1.6             // half-width of the neck where it meets the drop
    property real fall: 0               // how far the free drop has fallen
    property real dropOpacity: 1
    property bool detached: false

    function trigger() { if (!cycle.running) { next.stop(); cycle.start(); } }
    function scheduleNext() { next.interval = (7000 + Math.random() * 9000) * drip.calm; next.restart(); }
    Component.onCompleted: scheduleNext()
    Timer { id: next; onTriggered: cycle.start() }

    Shape {   // the neck: wide where it leaves the goop, thin where it ends in the drop
        visible: drip.neck > 0.05 && !drip.detached
        x: drip.dx
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: drip.color
            strokeWidth: -1
            PathSvg {
                path: "M -3.4 -1 L -3.4 0 Q " + (-drip.half) + " " + (drip.neck * 0.55) + " " + (-drip.half) + " " + drip.neck
                    + " L " + drip.half + " " + drip.neck + " Q " + drip.half + " " + (drip.neck * 0.55) + " 3.4 0 L 3.4 -1 Z"
            }
        }
    }
    Rectangle {   // the drop: round while it hangs, a little longer while it falls
        visible: drip.bulb > 0.1
        width: drip.bulb * 2
        height: drip.bulb * (drip.detached ? 2.8 : 2.2)
        radius: drip.bulb
        x: drip.dx - width / 2
        y: drip.neck + (drip.detached ? drip.fall : 0) - height / 2 + drip.bulb * 0.3
        color: drip.color
        opacity: drip.dropOpacity
    }

    SequentialAnimation {
        id: cycle
        ScriptAction { script: { drip.detached = false; drip.fall = 0; drip.dropOpacity = 1; drip.half = 1.6; drip.dx = (Math.random() - 0.5) * 8; } }
        ParallelAnimation {   // a bulge forms
            NumberAnimation { target: drip; property: "neck"; from: 0; to: 3; duration: 1100; easing.type: Easing.InOutQuad }
            NumberAnimation { target: drip; property: "bulb"; from: 0; to: 2.3; duration: 1100; easing.type: Easing.InOutQuad }
        }
        ParallelAnimation {   // it gets heavy: the neck stretches and thins
            NumberAnimation { target: drip; property: "neck"; to: 9; duration: 900; easing.type: Easing.InQuad }
            NumberAnimation { target: drip; property: "half"; to: 0.45; duration: 900 }
            NumberAnimation { target: drip; property: "bulb"; to: 2.9; duration: 900 }
        }
        ScriptAction { script: drip.detached = true }
        ParallelAnimation {   // let go: it falls with gravity and fades near the end
            NumberAnimation { target: drip; property: "fall"; to: 20; duration: 650; easing.type: Easing.InQuad }
            SequentialAnimation {
                PauseAnimation { duration: 380 }
                NumberAnimation { target: drip; property: "dropOpacity"; to: 0; duration: 270 }
            }
            NumberAnimation { target: drip; property: "bulb"; to: 2.0; duration: 650 }
        }
        ScriptAction { script: { drip.neck = 0; drip.bulb = 0; drip.detached = false; } }
        onFinished: drip.scheduleNext()
    }
}
