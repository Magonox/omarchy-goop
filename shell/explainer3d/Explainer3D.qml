import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import Quickshell
import Quickshell.Wayland
import "dam3d.js" as D

// The 3D explainer on Quick 3D: a transparent, input-less layer surface only as big as the picture, so the model floats over the desktop
// with no window around it. Geometry is built by code (ProceduralMesh); the storyboard (explainer/dam3d.js) says what happens at time t.
PanelWindow {
    id: ex
    property bool playing: false
    property real t: 0
    property real startedAt: 0
    readonly property var st: D.state(t)

    function play() { startedAt = Date.now(); t = 0; playing = true; }
    function stop() { playing = false; }

    visible: playing
    implicitWidth: 1000
    implicitHeight: 640
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "goop-explainer"
    mask: Region {}                       // no input region: every click goes through to the window underneath

    View3D {
        id: v3
        anchors.fill: parent
        camera: cam
        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.Medium
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowStrength: 0.35
            glowBloom: 0.2
            glowIntensity: 0.9
            glowHDRMinimumValue: 1.0
        }

        DirectionalLight { eulerRotation: Qt.vector3d(-48, 28, 0); brightness: 1.7; color: "#fff1dc"; castsShadow: true; shadowMapQuality: Light.ShadowMapQualityMedium; shadowFactor: 45; shadowMapFar: 90 }
        DirectionalLight { eulerRotation: Qt.vector3d(-20, -150, 0); brightness: 0.55; color: "#b8d4ff" }
        DirectionalLight { eulerRotation: Qt.vector3d(70, 20, 0); brightness: 0.25; color: "#ffffff" }

        Node {
            position: Qt.vector3d(ex.st.cam.target[0], ex.st.cam.target[1], ex.st.cam.target[2])
            eulerRotation: Qt.vector3d(-ex.st.cam.pitch, ex.st.cam.yaw, 0)
            PerspectiveCamera { id: cam; z: ex.st.cam.dist; fieldOfView: 34; clipNear: 0.5; clipFar: 300 }
        }

        Repeater3D {
            model: D.PARTS.length
            delegate: Model {
                id: m
                required property int index
                readonly property var part: D.PARTS[index]
                readonly property var s: ex.st.parts[index]
                geometry: ProceduralMesh { positions: D.positions(m.index); normals: D.normals(m.index); indexes: D.indexes(m.index) }
                position: Qt.vector3d(part.pos[0] + s.dx, part.pos[1] + s.dy, part.pos[2] + s.dz)
                scale: Qt.vector3d(s.sx, s.sy, s.sz)
                eulerRotation: Qt.vector3d(part.rot ? part.rot[0] : 0, s.rotY, part.rot ? part.rot[2] : 0)
                visible: s.vis
                castsShadows: !part.blend
                receivesShadows: true
                materials: PrincipledMaterial {
                    baseColor: Qt.rgba(m.part.color[0] / 255, m.part.color[1] / 255, m.part.color[2] / 255, 1)
                    metalness: m.part.metal
                    roughness: m.part.rough
                    opacity: m.part.blend ? (m.part.blend === 1 ? m.s.alpha : m.part.blend * m.s.alpha) : 1
                    alphaMode: m.part.blend ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
                    cullMode: PrincipledMaterial.NoCulling
                    emissiveFactor: Qt.vector3d(0.35 * m.s.glow, 0.12 * m.s.glow, 0.05 * m.s.glow)
                }
            }
        }

        Repeater3D {
            model: ex.st.drops.length
            delegate: Model {
                required property int index
                readonly property var d: ex.st.drops[index]
                source: "#Sphere"
                position: Qt.vector3d(d.x, d.y, d.z)
                scale: Qt.vector3d(d.s, d.s, d.s)
                visible: d.vis > 0 && d.s > 0.0002
                castsShadows: false
                materials: PrincipledMaterial { baseColor: "#8fd0ff"; emissiveFactor: Qt.vector3d(0.08, 0.2, 0.35); roughness: 0.1 }
            }
        }
        Repeater3D {
            model: ex.st.sparks.length
            delegate: Model {
                required property int index
                readonly property var d: ex.st.sparks[index]
                source: "#Sphere"
                position: Qt.vector3d(d.x, d.y, d.z)
                scale: Qt.vector3d(d.s, d.s, d.s)
                visible: d.s > 0.0002
                castsShadows: false
                materials: PrincipledMaterial { baseColor: "#fff2a0"; emissiveFactor: Qt.vector3d(1.1, 0.95, 0.25) }
            }
        }
    }

    Repeater {
        model: ex.st.labels.length
        delegate: Item {
            id: lab
            required property int index
            readonly property var l: ex.st.labels[index]
            readonly property var p: { var dep = ex.t; return v3.mapFrom3DScene(Qt.vector3d(l.at[0], l.at[1], l.at[2])); }
            opacity: l.a
            visible: l.a > 0.02
            Rectangle { x: 0; y: 0; width: 7; height: 7; radius: 3.5; color: "white"; anchors.centerIn: undefined; Component.onCompleted: {} }
            Canvas {
                anchors.fill: parent
            }
            Rectangle {
                id: pill
                x: lab.p.x + lab.l.dx - width / 2
                y: lab.p.y + lab.l.dy - height / 2
                width: txt.implicitWidth + 24; height: 28; radius: 14
                color: "#e6141822"
                border.color: "#55ffffff"; border.width: 1
                Text { id: txt; anchors.centerIn: parent; text: lab.l.text; color: "white"; font.pixelSize: 14; font.weight: Font.DemiBold }
            }
            Rectangle {   // the leader line, from the pill to the part
                x: Math.min(lab.p.x, pill.x + pill.width / 2); y: Math.min(lab.p.y, pill.y + pill.height / 2)
                width: 1; height: 1
                visible: false
            }
            Rectangle { x: lab.p.x - 4; y: lab.p.y - 4; width: 8; height: 8; radius: 4; color: "white"; border.color: "#88000000"; border.width: 1 }
        }
    }

    Timer {
        interval: 33; repeat: true; running: ex.playing
        onTriggered: { ex.t = (Date.now() - ex.startedAt) / 1000; if (ex.t >= D.DURATION) ex.stop(); }
    }
}
