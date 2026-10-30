// The 3D explainer as its own program, so a failure in Qt Quick 3D can only ever take down this window, never the Omarchy shell:
//   quickshell -n -p <plugin>/shell/explainer3d
// It plays once and exits.
import QtQuick
import Quickshell

ShellRoot {
    Explainer3D {
        id: ex
        Component.onCompleted: play()
        onPlayingChanged: if (!playing) Qt.quit()
    }
}
