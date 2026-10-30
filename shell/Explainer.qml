import QtQuick
import Quickshell
import Quickshell.Wayland
import "explainer/engine3d.js" as E3
import "explainer/dam.js" as Dam

// A windowless 3D explainer: a transparent full-screen layer surface that takes no input, with a plain-JS 3D renderer drawing onto a canvas
// in the middle. Playback is driven by time, so a storyboard is just a function t -> scene (see explainer/dam.js).
PanelWindow {
    id: ex
    property bool playing: false
    property real t: 0
    property real startedAt: 0

    function play() { startedAt = Date.now(); t = 0; playing = true; }
    function stop() { playing = false; }

    visible: playing
    // No anchors: the compositor centres a surface that is only as big as the picture, so a frame redraws ~1/4 of the screen's pixels.
    implicitWidth: 900
    implicitHeight: 560
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "goop-explainer"
    mask: Region {}                       // an empty input region: every click goes through to whatever is underneath

    Canvas {
        id: cv
        width: 860; height: 520
        anchors.centerIn: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            if (ex.playing) E3.render(ctx, width, height, Dam.scene(ex.t));
        }
    }
    Timer {
        interval: 41; repeat: true; running: ex.playing
        onTriggered: {
            ex.t = (Date.now() - ex.startedAt) / 1000;
            if (ex.t >= Dam.DURATION) ex.stop(); else cv.requestPaint();
        }
    }
}
