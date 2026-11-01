import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// The first-run setup card: five short steps, a centred card, Back / Next. It opens by itself once (Goop.qml: setup_version is 0), and again from
// the bar panel's "Run setup again". Every choice is written through daemon/settings.py, the same path the bar panel uses, so the two always agree.
// Nothing here is required: closing the card (x) skips it, and every step says plainly what is missing and how to fix it.
PanelWindow {
    id: wz
    required property var app                 // the Goop overlay window (settings state and helpers)
    required property var paths               // the Goop scope (where the plugin lives)
    property int step: 0
    readonly property int steps: 5
    property var checks: []
    property bool installing: false
    property string installWhat: ""
    property string installLine: ""
    property string installDone: ""
    readonly property color accent: "#e84a52"
    readonly property color ink: "#f0f0f4"
    readonly property color dim: "#9a9aa6"
    readonly property color panel: "#fb141418"

    visible: app.wizardOpen
    implicitWidth: 580
    implicitHeight: 524
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "goop-setup"

    onVisibleChanged: if (visible) { step = 0; installDone = ""; refresh(); }

    function set(key, value) { Quickshell.execDetached(["python3", paths.daemon + "/settings.py", "set", key, String(value)]); }
    function refresh() { if (!doctor.running) doctor.running = true; }
    function check(id) { for (var i = 0; i < checks.length; i++) if (checks[i].id === id) return checks[i]; return null; }
    function ok(id) { var c = check(id); return !!c && c.ok; }
    function finish() { set("setup_version", 1); app.wizardOpen = false; }
    function run(what, cmd) {
        if (installing) return;
        installWhat = what; installLine = "Starting..."; installDone = ""; installing = true;
        installer.command = cmd;
        installer.running = true;
    }
    function tidy(line) { return line.replace(/\x1b\[[0-9;]*m/g, "").trim(); }
    // the packages Goop's optional 3D lessons need, as one command to copy (Goop never runs sudo itself)
    readonly property string pacmanLine: {
        var pk = [];
        if (!ok("quick3d")) pk.push("qt6-quick3d");
        if (!ok("sandbox")) pk.push("deno");
        return pk.length ? "sudo pacman -S " + pk.join(" ") : "";
    }

    Process {
        id: doctor
        command: ["python3", wz.paths.daemon + "/doctor.py"]
        stdout: StdioCollector { onStreamFinished: { try { wz.checks = JSON.parse(text).checks; } catch (e) {} } }
    }
    Process {
        id: installer
        stdout: SplitParser { onRead: line => { var t = wz.tidy(line); if (t) wz.installLine = t; } }
        stderr: SplitParser { onRead: line => { var t = wz.tidy(line); if (t) wz.installLine = t; } }
        onExited: (code) => {
            wz.installing = false;
            wz.installDone = code === 0 ? (wz.installWhat === "page reader" ? "Done. Restart Chromium to load it." : "Done.") : "That did not finish (see " + wz.installWhat + " in the terminal docs).";
            wz.refresh();
            if (wz.installWhat !== "page reader") wz.app.reloadVoice();
        }
    }

    // ---- small building blocks ----
    component Pill: Rectangle {
        id: pill
        property alias text: label.text
        property bool primary: false
        property bool enabled: true
        signal clicked()
        implicitWidth: label.implicitWidth + 32; implicitHeight: 34; radius: 17
        opacity: enabled ? 1 : 0.4
        color: primary ? (ma.containsMouse && enabled ? Qt.lighter(wz.accent, 1.12) : wz.accent) : (ma.containsMouse && enabled ? "#2c2c33" : "transparent")
        border.width: primary ? 0 : 1
        border.color: "#4a4a54"
        Text { id: label; anchors.centerIn: parent; color: pill.primary ? "white" : wz.ink; font.pixelSize: 13; font.weight: pill.primary ? Font.DemiBold : Font.Normal }
        MouseArea { id: ma; anchors.fill: parent; enabled: pill.enabled; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.clicked() }
    }
    component Switch: Rectangle {
        id: sw
        property bool on: false
        property bool enabled: true
        signal toggled()
        width: 42; height: 24; radius: 12
        opacity: enabled ? 1 : 0.4
        color: on ? wz.accent : "#3a3a44"
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle { y: 3; x: sw.on ? 21 : 3; width: 18; height: 18; radius: 9; color: "white"; Behavior on x { NumberAnimation { duration: 120 } } }
        MouseArea { anchors.fill: parent; enabled: sw.enabled; cursorShape: Qt.PointingHandCursor; onClicked: sw.toggled() }
    }
    component Choice: Rectangle {
        id: ch
        property string title: ""
        property string note: ""
        property bool selected: false
        signal picked()
        width: parent ? parent.width : 400
        height: 44; radius: 10
        color: selected ? "#2a2024" : (ma2.containsMouse ? "#202026" : "transparent")
        border.width: 1; border.color: selected ? wz.accent : "#34343c"
        Rectangle { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 14; height: 14; radius: 7; color: "transparent"; border.width: 2; border.color: ch.selected ? wz.accent : "#5a5a64"
            Rectangle { anchors.centerIn: parent; width: 6; height: 6; radius: 3; color: wz.accent; visible: ch.selected } }
        Column {
            x: 38; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 50; spacing: 1
            Text { text: ch.title; color: wz.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
            Text { text: ch.note; color: wz.dim; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
        }
        MouseArea { id: ma2; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ch.picked() }
    }

    Rectangle {
        anchors.fill: parent
        radius: 18
        color: wz.panel
        border.width: 1
        border.color: Qt.alpha(wz.accent, 0.7)

        // header: the goop, the step title and a way out
        Item {
            id: head
            x: 24; y: 20; width: parent.width - 48; height: 40
            Rectangle {   // a small goop
                width: 38; height: 34; radius: 15; color: wz.accent
                Rectangle { x: 10; y: 11; width: 4.5; height: 9; radius: 2.2; color: "white" }
                Rectangle { x: 23; y: 11; width: 4.5; height: 9; radius: 2.2; color: "white" }
            }
            Text {
                x: 52; anchors.verticalCenter: parent.verticalCenter
                text: ["Meet Goop", "Check your setup", "Voice", "Safety and 3D lessons", "Try it"][wz.step]
                color: wz.ink; font.pixelSize: 20; font.weight: Font.DemiBold
            }
            Text {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                text: "Skip setup"; color: wz.dim; font.pixelSize: 12
                MouseArea { anchors.fill: parent; anchors.margins: -8; cursorShape: Qt.PointingHandCursor; onClicked: wz.finish() }
            }
        }

        // ---------- 1: meet goop ----------
        Column {
            visible: wz.step === 0
            x: 24; y: 82; width: parent.width - 48; spacing: 14
            Text {
                width: parent.width; wrapMode: Text.Wrap; color: wz.ink; font.pixelSize: 15; lineHeight: 1.25
                text: "A small creature that lives on your windows. Click it to ask about what is in that window, by talking or typing. It can look, explain, build 3D lessons and, with your OK, do things."
            }
            Repeater {
                model: [
                    { t: "Your voice stays on your computer", d: "Speaking and listening run on this machine. The microphone is only open while you talk." },
                    { t: "Nothing happens without your OK", d: "Actions show a card with exactly what will happen. You choose how careful it is, next." },
                    { t: "It only looks when you ask", d: "Your agent (Claude Code) sees a window when you ask about it, never in the background." }
                ]
                delegate: Row {
                    required property var modelData
                    width: parent.width; spacing: 12
                    Text { text: "✓"; color: wz.accent; font.pixelSize: 16; font.weight: Font.Bold }
                    Column {
                        width: parent.width - 30; spacing: 2
                        Text { text: modelData.t; color: wz.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Text { text: modelData.d; color: wz.dim; font.pixelSize: 12; width: parent.width; wrapMode: Text.Wrap }
                    }
                }
            }
        }

        // ---------- 2: checks ----------
        Column {
            visible: wz.step === 1
            x: 24; y: 78; width: parent.width - 48; spacing: 8
            Text { text: "NEEDED"; color: wz.dim; font.pixelSize: 11; font.letterSpacing: 1 }
            Repeater {
                model: wz.checks.filter(function (c) { return c.required; })
                delegate: Column {
                    required property var modelData
                    width: parent.width; spacing: 1
                    Row {
                        spacing: 8
                        Text { text: modelData.ok ? "✓" : "✗"; color: modelData.ok ? "#6fcf8a" : wz.accent; font.pixelSize: 14; font.weight: Font.Bold }
                        Text { text: modelData.label; color: wz.ink; font.pixelSize: 13 }
                    }
                    Text { visible: !modelData.ok; x: 22; width: parent.width - 22; wrapMode: Text.Wrap; text: modelData.hint; color: wz.dim; font.pixelSize: 11 }
                }
            }
            Item { width: 1; height: 4 }
            Text { text: "EXTRAS"; color: wz.dim; font.pixelSize: 11; font.letterSpacing: 1 }
            Grid {
                width: parent.width; columns: 2; columnSpacing: 12; rowSpacing: 5
                Repeater {
                    model: wz.checks.filter(function (c) { return !c.required; })
                    delegate: Row {
                        required property var modelData
                        width: (parent.width - 12) / 2; spacing: 7
                        Text { text: modelData.ok ? "✓" : "○"; color: modelData.ok ? "#6fcf8a" : wz.dim; font.pixelSize: 13 }
                        Text { width: parent.width - 22; text: modelData.label; color: modelData.ok ? wz.ink : wz.dim; font.pixelSize: 11; elide: Text.ElideRight }
                    }
                }
            }
            Item { width: 1; height: 2 }
            Flow {
                width: parent.width; spacing: 8
                Pill { visible: !wz.ok("voice") || !wz.ok("listen"); text: "Install voice and talking"; primary: true; enabled: !wz.installing
                       onClicked: wz.run("voice", ["bash", wz.paths.here + "/../setup.sh"]) }
                Pill { visible: !wz.ok("pagereader"); text: "Install the page reader"; enabled: !wz.installing
                       onClicked: wz.run("page reader", ["bash", wz.paths.here + "/../bin/goop-install-pagereader"]) }
                Pill { text: "Check again"; enabled: !wz.installing; onClicked: wz.refresh() }
            }
            Text {
                visible: wz.installing || wz.installDone !== ""
                width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11
                color: wz.installing ? wz.dim : "#6fcf8a"
                text: wz.installing ? ("Installing " + wz.installWhat + ": " + wz.installLine) : wz.installDone
            }
            Text {
                visible: wz.pacmanLine !== ""
                width: parent.width; wrapMode: Text.Wrap; color: wz.dim; font.pixelSize: 11
                text: "For 3D lessons, run this in a terminal:  " + wz.pacmanLine
            }
        }

        // ---------- 3: voice ----------
        Column {
            visible: wz.step === 2
            x: 24; y: 84; width: parent.width - 48; spacing: 16
            Row {
                width: parent.width; spacing: 12
                Column {
                    width: parent.width - 60; spacing: 2
                    Text { text: "Goops speak their answers"; color: wz.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { width: parent.width; wrapMode: Text.Wrap; color: wz.dim; font.pixelSize: 12
                           text: wz.ok("voice") ? "A friendly voice reads each reply. Each goop gets its own." : "The voice is not installed yet. Go back one step and tap Install voice and talking." }
                }
                Switch { on: !wz.app.muted; enabled: wz.ok("voice"); onToggled: wz.set("tts.muted", wz.app.muted ? "false" : "true") }
            }
            Row {
                width: parent.width; spacing: 12
                Column {
                    width: parent.width - 60; spacing: 2
                    Text { text: "Talk to goops"; color: wz.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { width: parent.width; wrapMode: Text.Wrap; color: wz.dim; font.pixelSize: 12
                           text: wz.ok("listen") ? "Click a goop, then Talk. The microphone is open only while you talk, and nothing is recorded or sent anywhere." : "Speech recognition is not installed yet. Go back one step and tap Install voice and talking." }
                }
                Switch { on: wz.app.sttEnabled; enabled: wz.ok("listen"); onToggled: wz.set("stt.enabled", wz.app.sttEnabled ? "false" : "true") }
            }
            Pill {
                text: "Hear a goop"; enabled: wz.app.ttsReady && !wz.app.muted && wz.app.perched.length > 0
                onClicked: wz.app.speak(wz.app.perched[0], "Hi! I am a goop. Click me, then choose Talk or Type, and ask me anything.")
            }
        }

        // ---------- 4: safety and 3D lessons ----------
        Column {
            visible: wz.step === 3
            x: 24; y: 76; width: parent.width - 48; spacing: 6
            Text { text: "HOW CAREFUL SHOULD GOOP BE?"; color: wz.dim; font.pixelSize: 11; font.letterSpacing: 1 }
            Repeater {
                model: [
                    { k: "ask", t: "Ask first (recommended)", d: "Asks before it acts. Plain read-only commands like ls run at once." },
                    { k: "ask_all", t: "Ask for everything", d: "A card before every action, file read and screenshot." },
                    { k: "look", t: "Look only", d: "It can see and read, but never change anything." }
                ]
                delegate: Choice { required property var modelData; title: modelData.t; note: modelData.d; selected: wz.app.access === modelData.k; onPicked: wz.set("access", modelData.k) }
            }
            Item { width: 1; height: 4 }
            Text { text: "3D LESSONS"; color: wz.dim; font.pixelSize: 11; font.letterSpacing: 1 }
            Repeater {
                model: [
                    { k: "offer", t: "Ask me first (recommended)", d: "Goop offers a 3D lesson of what you are reading; a card asks before it builds." },
                    { k: "auto", t: "Build automatically", d: "Builds one whenever it thinks it would help." },
                    { k: "never", t: "Off", d: "Goop only explains in words." }
                ]
                delegate: Choice { required property var modelData; title: modelData.t; note: modelData.d; selected: wz.app.explainers === modelData.k; onPicked: wz.set("explainers", modelData.k) }
            }
            Text { width: parent.width; wrapMode: Text.Wrap; color: wz.dim; font.pixelSize: 11
                   text: "A lesson takes about a minute to build and uses your Claude plan (roughly 20 to 40 cents on the API)." }
        }

        // ---------- 5: try it ----------
        Column {
            visible: wz.step === 4
            x: 24; y: 84; width: parent.width - 48; spacing: 16
            Text { width: parent.width; wrapMode: Text.Wrap; color: wz.ink; font.pixelSize: 15; lineHeight: 1.25
                   text: "Click the goop at the top of a window. Two buttons appear beside it:" }
            Row {
                spacing: 36; anchors.horizontalCenter: parent.horizontalCenter
                Column {
                    spacing: 6
                    Rectangle { width: 54; height: 54; radius: 27; color: "#1c1c22"; border.width: 1.5; border.color: Qt.alpha(wz.accent, 0.85); anchors.horizontalCenter: parent.horizontalCenter
                        MicGlyph { anchors.centerIn: parent; scale: 1.5 } }
                    Text { text: "Talk"; color: wz.ink; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.horizontalCenter: parent.horizontalCenter }
                }
                Column {
                    spacing: 6
                    Rectangle { width: 54; height: 54; radius: 27; color: "#1c1c22"; border.width: 1.5; border.color: Qt.alpha(wz.accent, 0.85); anchors.horizontalCenter: parent.horizontalCenter
                        PencilGlyph { anchors.centerIn: parent; scale: 1.5 } }
                    Text { text: "Type"; color: wz.ink; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.horizontalCenter: parent.horizontalCenter }
                }
            }
            Text { width: parent.width; wrapMode: Text.Wrap; color: wz.dim; font.pixelSize: 13; lineHeight: 1.25
                   text: "Try: \"Explain how this page works with a 3D model.\"  You can drag a goop onto another window to give it a copy, and change anything later from the ghost icon in the bar." }
        }

        // footer: dots, Back, Next
        Item {
            x: 24; y: parent.height - 62; width: parent.width - 48; height: 36
            Pill { visible: wz.step > 0; text: "Back"; onClicked: wz.step -= 1 }
            Row {
                anchors.centerIn: parent; spacing: 7
                Repeater { model: wz.steps; delegate: Rectangle { required property int index; width: index === wz.step ? 18 : 7; height: 7; radius: 3.5; color: index === wz.step ? wz.accent : "#4a4a54"
                                                                  Behavior on width { NumberAnimation { duration: 120 } } } }
            }
            Pill {
                anchors.right: parent.right
                primary: true
                text: wz.step === wz.steps - 1 ? "Finish" : (wz.step === 0 ? "Get started" : "Next")
                onClicked: { if (wz.step === wz.steps - 1) wz.finish(); else { wz.step += 1; if (wz.step === 1) wz.refresh(); } }
            }
        }
    }
}
