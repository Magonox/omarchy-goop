import QtQuick

// A goop's eyes, drawn around (0,0) of a zero-size item so the parent just positions it at the goop's center.
// Personality (spacing, size, round vs pill, tilt, blink rhythm) is derived from `seed`, so no two goops match.
Item {
    id: eyes
    property int seed: 0
    property real gx: 0                 // gaze direction, -1..1
    property real gy: 0
    property string mood: "idle"        // idle | startled | thinking | happy | error

    readonly property real half: 4.2 + (seed % 5) * 0.55
    readonly property real baseW: 2.6 + (seed % 3) * 0.45
    readonly property bool round: seed % 4 === 3
    readonly property real baseH: round ? baseW * 1.9 : 7 + Math.floor(seed / 7) % 3
    readonly property real tilt: (Math.floor(seed / 5) % 5 - 2) * 3
    readonly property int blinkBase: 2400 + (seed % 7) * 650

    property real wander: 0             // thinking: eyes scan side to side
    property bool shut: false

    readonly property real wMul: mood === "startled" ? 1.15 : mood === "happy" ? 1.5 : 1
    readonly property real hMul: mood === "startled" ? 1.3 : mood === "happy" ? 0.35 : mood === "error" ? 0.8 : mood === "thinking" ? 0.9 : 1
    readonly property real lean: mood === "error" ? 14 : 0
    readonly property real dropY: mood === "error" ? 2 : 0
    readonly property real lookX: mood === "thinking" ? wander * 0.85 : (mood === "startled" || mood === "happy") ? 0 : gx
    readonly property real lookY: mood === "thinking" ? -0.5 : (mood === "startled" || mood === "happy") ? 0 : gy

    property real sx: lookX
    property real sy: lookY
    Behavior on sx { NumberAnimation { duration: 90 } }
    Behavior on sy { NumberAnimation { duration: 90 } }

    Item {
        rotation: eyes.tilt
        Repeater {
            model: [-1, 1]
            delegate: Rectangle {
                property real w: eyes.baseW * eyes.wMul
                property real h: eyes.shut ? 1.2 : eyes.baseH * eyes.hMul
                width: w; height: h
                radius: Math.min(w, h) / 2
                color: "white"
                x: modelData * eyes.half - w / 2 + eyes.sx * 2.8
                y: -h / 2 + eyes.sy * 2.8 + eyes.dropY
                rotation: modelData * -eyes.lean
                Behavior on w { NumberAnimation { duration: 90 } }
                Behavior on h { NumberAnimation { duration: 70 } }
            }
        }
    }

    // blink at the goop's own rhythm, sometimes twice in a row
    Timer {
        id: blinkT
        onTriggered: { eyes.shut = true; openT.start() }
    }
    Timer {
        id: openT
        interval: 110
        onTriggered: {
            eyes.shut = false;
            blinkT.interval = Math.random() < 0.2 ? 160 : eyes.blinkBase * (0.6 + Math.random() * 0.8);
            blinkT.start();
        }
    }
    Component.onCompleted: { blinkT.interval = blinkBase * (0.3 + Math.random()); blinkT.start() }

    SequentialAnimation {
        running: eyes.mood === "thinking"
        loops: Animation.Infinite
        NumberAnimation { target: eyes; property: "wander"; to: 1; duration: 700; easing.type: Easing.InOutSine }
        NumberAnimation { target: eyes; property: "wander"; to: -1; duration: 1400; easing.type: Easing.InOutSine }
        NumberAnimation { target: eyes; property: "wander"; to: 0; duration: 700; easing.type: Easing.InOutSine }
        onStopped: eyes.wander = 0
    }
}
