import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "lesson.js" as L
import "shapes.js" as S
import "meshes.js" as M

// Plays any resolved scene (daemon/goop/explainer) as a windowless 3D lesson: a transparent, input-less layer surface sized to the picture.
// GOOP_SPEED=4 plays it four times faster (for testing).
PanelWindow {
    id: ex
    property var scene: null
    property bool playing: false
    property real t: 0
    property real startedAt: 0
    readonly property real speed: Number(Quickshell.env("GOOP_SPEED") || 1)
    // GOOP_CLOCK_FILE=/path: the lesson time is read from this file (a number of seconds) instead of the wall clock, so a script can step the lesson frame by frame
    // (used to film smooth footage). The picture is a pure function of the time, so the same number always gives the same frame.
    readonly property string clockFile: Quickshell.env("GOOP_CLOCK_FILE")
    readonly property var ctx: scene ? L.prepare(scene) : null
    readonly property var st: ctx ? L.state(ctx, t) : null
    readonly property var subs: scene ? scene.parts.map(function (p) { return S.build(p.shape); }) : []
    readonly property var ringMesh: M.torus(1.0, 0.012, 64, 6)

    // GOOP_START=95 starts the lesson 95 seconds in (for testing the ending)
    function play() { startedAt = Date.now() - Number(Quickshell.env("GOOP_START") || 0) * 1000 / speed; t = 0; playing = true; }
    function stop() { playing = false; }

    visible: playing && !!scene
    implicitWidth: 1000
    implicitHeight: 640
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "goop-explainer"
    mask: Region { item: closeBtn }       // only the close button takes clicks: everything else goes through to the window underneath

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

        DirectionalLight { eulerRotation: Qt.vector3d(-48, 28, 0); brightness: 1.7; color: "#fff1dc"; castsShadow: true; shadowMapQuality: Light.ShadowMapQualityMedium; shadowFactor: 40; shadowMapFar: 60 }
        DirectionalLight { eulerRotation: Qt.vector3d(-20, -150, 0); brightness: 0.6; color: "#b8d4ff" }
        DirectionalLight { eulerRotation: Qt.vector3d(70, 20, 0); brightness: 0.3; color: "#ffffff" }

        Node {
            position: ex.st ? Qt.vector3d(ex.st.cam.target[0], ex.st.cam.target[1], ex.st.cam.target[2]) : Qt.vector3d(0, 0, 0)
            eulerRotation: ex.st ? Qt.vector3d(-ex.st.cam.pitch, ex.st.cam.yaw, 0) : Qt.vector3d(0, 0, 0)
            PerspectiveCamera { id: cam; z: ex.st ? ex.st.cam.dist : 20; fieldOfView: 34; clipNear: 0.5; clipFar: 300 }
        }

        Node {      // the whole assembled body: the finale moves, rolls and sinks it as one
            id: modelRoot
            pivot: ex.st ? Qt.vector3d(ex.st.root.pivot[0], ex.st.root.pivot[1], ex.st.root.pivot[2]) : Qt.vector3d(0, 0, 0)
            position: ex.st ? Qt.vector3d(ex.st.root.pos[0], ex.st.root.pos[1], ex.st.root.pos[2]) : Qt.vector3d(0, 0, 0)
            eulerRotation: ex.st ? Qt.vector3d(ex.st.root.rot[0], ex.st.root.rot[1], ex.st.root.rot[2]) : Qt.vector3d(0, 0, 0)
        Repeater3D {
            model: ex.scene ? ex.scene.parts.length : 0
            delegate: Node {
                id: pn
                required property int index
                readonly property var part: ex.scene.parts[index]
                readonly property var s: ex.st.parts[index]
                position: Qt.vector3d(part.pos[0] + s.dx, part.pos[1] + s.dy, part.pos[2] + s.dz)
                eulerRotation: Qt.vector3d(part.rot[0], part.rot[1], part.rot[2])
                scale: Qt.vector3d(s.k, s.k, s.k)
                visible: s.vis
                property var subs: ex.subs[index] || []      // the part's drawable pieces; a code part's file replaces them when it fills in
                FileView {      // a part whose geometry is still being written: it appears the moment its file has meshes in it
                    path: pn.part.shape.file || ""
                    watchChanges: true
                    onFileChanged: reload()
                    onLoaded: {
                        try {
                            var d = JSON.parse(text());
                            if (d.meshes && d.meshes.length) pn.subs = S.meshSubs(d.meshes, d.scale);
                        } catch (e) { console.log("GOOP-EXPLAINER: bad part file:", e); }
                    }
                }
                Node {
                    // spinning turns the part about its own axis: a wheel about its axle, a rotor about the vertical
                    eulerRotation: { var ax = pn.part.spin_axis || [0, 1, 0]; return Qt.vector3d(ax[0] * pn.s.spin, ax[1] * pn.s.spin, ax[2] * pn.s.spin); }
                    Repeater3D {
                        model: pn.subs.length
                        delegate: Model {
                            id: md
                            required property int index
                            readonly property var sub: pn.subs[index]
                            readonly property var mat: L.material(pn.part, sub.role, pn.s)
                            geometry: ProceduralMesh { positions: M.vecs(md.sub.mesh.p); normals: M.vecs(md.sub.mesh.n); indexes: md.sub.mesh.i }
                            castsShadows: md.mat.alpha > 0.9
                            receivesShadows: true
                            materials: PrincipledMaterial {
                                baseColor: Qt.rgba(md.mat.r, md.mat.g, md.mat.b, 1)
                                metalness: md.mat.metal
                                roughness: md.mat.rough
                                opacity: md.mat.alpha
                                alphaMode: md.mat.alpha < 0.995 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
                                cullMode: PrincipledMaterial.NoCulling
                                emissiveFactor: Qt.vector3d(md.mat.er, md.mat.eg, md.mat.eb)
                            }
                        }
                    }
                }
            }
        }

        }

        Repeater3D {   // flowing air, fuel, exhaust, water
            model: 64
            delegate: Model {
                required property int index
                readonly property var d: ex.st && index < ex.st.drops.length ? ex.st.drops[index] : null
                source: "#Sphere"
                visible: d !== null
                position: d ? Qt.vector3d(d.x, d.y, d.z) : Qt.vector3d(0, 0, 0)
                scale: d ? Qt.vector3d(d.s, d.s, d.s) : Qt.vector3d(0, 0, 0)
                castsShadows: false
                materials: PrincipledMaterial { baseColor: d ? Qt.rgba(d.r, d.g, d.b, 1) : "white"; emissiveFactor: d ? Qt.vector3d(d.r * 0.5, d.g * 0.5, d.b * 0.5) : Qt.vector3d(0, 0, 0); roughness: 0.2 }
            }
        }

        Repeater3D {   // radio waves spreading like ripples in a pond
            model: 8
            delegate: Model {
                required property int index
                readonly property var d: ex.st && index < ex.st.rings.length ? ex.st.rings[index] : null
                geometry: ProceduralMesh { positions: M.vecs(ex.ringMesh.p); normals: M.vecs(ex.ringMesh.n); indexes: ex.ringMesh.i }
                visible: d !== null
                position: d ? Qt.vector3d(d.x, d.y, d.z) : Qt.vector3d(0, 0, 0)
                scale: d ? Qt.vector3d(d.radius, 1, d.radius) : Qt.vector3d(0, 0, 0)
                castsShadows: false
                materials: PrincipledMaterial {
                    baseColor: "#9fdcff"; emissiveFactor: Qt.vector3d(0.25, 0.6, 0.9)
                    opacity: d ? d.a : 0; alphaMode: PrincipledMaterial.Blend; cullMode: PrincipledMaterial.NoCulling
                }
            }
        }

        Repeater3D {   // the finale's flame, smoke, bubbles, dust and contrails
            model: 96
            delegate: Model {
                required property int index
                readonly property var d: ex.st && index < ex.st.fx.length ? ex.st.fx[index] : null
                source: "#Sphere"
                visible: d !== null
                position: d ? Qt.vector3d(d.x, d.y, d.z) : Qt.vector3d(0, 0, 0)
                scale: d ? Qt.vector3d(d.s, d.s, d.s) : Qt.vector3d(0, 0, 0)
                castsShadows: false
                materials: PrincipledMaterial {
                    baseColor: d ? Qt.rgba(d.r, d.g, d.b, 1) : "white"
                    emissiveFactor: d ? Qt.vector3d(d.r * d.em, d.g * d.em, d.b * d.em) : Qt.vector3d(0, 0, 0)
                    roughness: 0.9
                    opacity: d ? d.a : 0
                    alphaMode: PrincipledMaterial.Blend
                }
            }
        }

        Model {   // the finale's prop: a launch pad, a road, or the surface of the sea
            id: envModel
            readonly property var e: ex.st ? ex.st.env : null
            source: "#Cube"
            visible: e !== null
            position: e ? Qt.vector3d(e.pos[0], e.pos[1], e.pos[2]) : Qt.vector3d(0, 0, 0)
            scale: e ? Qt.vector3d(e.size[0] / 100, e.size[1] / 100, e.size[2] / 100) : Qt.vector3d(0, 0, 0)
            castsShadows: false
            receivesShadows: true
            materials: PrincipledMaterial {
                baseColor: envModel.e ? Qt.rgba(envModel.e.color[0], envModel.e.color[1], envModel.e.color[2], 1) : "white"
                roughness: 0.8
                opacity: envModel.e ? envModel.e.a : 0
                alphaMode: PrincipledMaterial.Blend
            }
        }

        Repeater3D {   // signal bars above each device
            model: ex.ctx ? ex.ctx.bars.length : 0
            delegate: Model {
                required property int index
                readonly property var b: ex.st.bars[index]
                source: "#Cube"
                visible: b.vis
                position: Qt.vector3d(b.x, b.y, b.z)
                scale: Qt.vector3d(b.w / 100, b.h / 100, b.w / 100)
                castsShadows: false
                materials: PrincipledMaterial { baseColor: Qt.rgba(b.r, b.g, b.b, 1); emissiveFactor: Qt.vector3d(b.r * b.em, b.g * b.em, b.b * b.em); roughness: 0.4 }
            }
        }
    }

    Repeater {
        model: ex.st ? ex.st.labels.length : 0
        delegate: Item {
            id: lab
            required property int index
            readonly property var l: ex.st.labels[index]
            readonly property var p: { var dep = ex.t; return v3.mapFrom3DScene(Qt.vector3d(l.at[0], l.at[1], l.at[2])); }
            opacity: l.a
            Rectangle {
                id: pill
                x: lab.p.x - width / 2
                y: lab.p.y - 52 - height / 2
                width: txt.implicitWidth + 24; height: 28; radius: 14
                color: "#e6141822"
                border.color: "#55ffffff"; border.width: 1
                Text { id: txt; anchors.centerIn: parent; text: lab.l.text; color: "white"; font.pixelSize: 14; font.weight: Font.DemiBold }
            }
            Rectangle { x: lab.p.x - 0.5; y: lab.p.y - 38; width: 1; height: 38; color: "#99ffffff" }
            Rectangle { x: lab.p.x - 4; y: lab.p.y - 4; width: 8; height: 8; radius: 4; color: "white"; border.color: "#88000000"; border.width: 1 }
        }
    }

    FileView {
        path: ex.clockFile
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: { var v = parseFloat(text()); if (!isNaN(v)) ex.t = v; }
    }

    Rectangle {     // the only way to end a lesson early (also: goopctl explain3d stop)
        id: closeBtn
        visible: ex.clockFile === ""            // not in filmed footage
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: 14; anchors.topMargin: 10
        width: closeTxt.implicitWidth + 24; height: 28; radius: 14
        color: closeMa.containsMouse ? "#f0303844" : "#b0141822"
        border.color: "#55ffffff"; border.width: 1
        opacity: closeMa.containsMouse ? 1 : 0.7
        Text { id: closeTxt; anchors.centerIn: parent; text: "✕  Close lesson"; color: "white"; font.pixelSize: 13 }
        MouseArea { id: closeMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ex.stop() }
    }

    Timer {
        interval: 33; repeat: true; running: ex.playing
        onTriggered: { if (ex.clockFile !== "") return; ex.t = (Date.now() - ex.startedAt) / 1000 * ex.speed; if (ex.scene && ex.t >= ex.scene.duration) ex.stop(); }
    }
}
