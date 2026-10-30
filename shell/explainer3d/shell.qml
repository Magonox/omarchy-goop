// The 3D explainer as its own program, so a failure in Qt Quick 3D can only ever take down this window, never the Omarchy shell:
//   GOOP_SCENE=/path/to/scene.json quickshell -n -p <plugin>/shell/explainer3d     (a lesson built by daemon/build_scene.py)
//   quickshell -n -p <plugin>/shell/explainer3d                                    (no scene: the original hand-built dam)
// It plays once and exits. bin/goop-explain does all of this.
import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root
    readonly property string scenePath: Quickshell.env("GOOP_SCENE")

    Explainer3D {   // the original dam
        id: dam
        Component.onCompleted: if (root.scenePath === "") play()
        onPlayingChanged: if (!playing) Qt.quit()
    }
    Lesson3D {
        id: lesson
        onPlayingChanged: if (!playing) Qt.quit()
    }
    FileView {
        path: root.scenePath
        printErrors: true
        onLoaded: {
            try { lesson.scene = JSON.parse(text()); lesson.play(); }
            catch (e) { console.log("GOOP-EXPLAINER: bad scene file:", e); Qt.quit(); }
        }
        onLoadFailed: { if (root.scenePath !== "") { console.log("GOOP-EXPLAINER: cannot read the scene file"); Qt.quit(); } }
    }
}
