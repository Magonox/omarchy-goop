import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "goo.js" as Goo

// Goop: lives on windows. The first active window gets one; drag any goop onto another window to peel off a copy.
Scope {
    id: root

    // Where this plugin lives, so it works both as an Omarchy plugin (where the shell's own directory is Omarchy's, not ours)
    // and standalone. Everything below uses plain paths: Process commands are not sandboxed by Quickshell's file layer.
    readonly property string here: Qt.resolvedUrl("Goop.qml").toString().replace("file://", "").replace(/\/[^\/]*$/, "")
    readonly property string daemon: here + "/../daemon"
    // The bar widget's settings panel (GoopPanel.qml) cannot reach this overlay directly (third-party plugins only get scoped
    // shell facades), so the live state is published to a small file that the panel watches.
    // A string, so it only "changes" when the state really does (an object would re-fire on every dependency re-evaluation).
    readonly property string statusJson: JSON.stringify({ goops: win.perched.length, voiceReady: win.ttsReady, muted: win.muted,
                                                          animations: win.animations, enabled: win.gooEnabled, provider: win.provider, access: win.access, explainers: win.explainers, voiceInput: win.sttEnabled })
    readonly property string statusPath: Quickshell.env("HOME") + "/.cache/goop/status.json"
    onStatusJsonChanged: statusWrite.restart()
    Timer {
        id: statusWrite
        interval: 300
        onTriggered: Quickshell.execDetached(["bash", "-c", "mkdir -p \"$(dirname \"$2\")\" && printf '%s' \"$1\" > \"$2.tmp\" && mv \"$2.tmp\" \"$2\"",
                                              "_", root.statusJson, root.statusPath])
    }
    function screenFor(name) {          // the Quickshell screen with this name (the first one when unknown)
        var ss = Quickshell.screens;
        for (var i = 0; i < ss.length; i++) if (ss[i].name === name) return ss[i];
        return ss.length ? ss[0] : null;
    }
    function setSetting(key, value) { Quickshell.execDetached(["python3", root.daemon + "/settings.py", "set", key, String(value)]); }

    Explainer { id: explainer }

    readonly property string venvPython: Quickshell.env("HOME") + "/.local/share/goop/venv/bin/python"   // created by setup.sh

PanelWindow {
    id: win
    screen: root.screenFor(win.monName)
    visible: win.gooEnabled
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "goop"

    readonly property int maxGoops: 8
    readonly property real r: 13            // goop radius
    readonly property var palette: ["#e5484d", "#3e63dd", "#30a46c", "#f5a524", "#8e4ec6", "#12a594", "#e93d82", "#f76b15"]

    property var perched: []                // addresses of windows that have a goop
    property var colors: ({})               // address -> color
    property var seeds: ({})                // address -> personality seed (eyes, blink rhythm, squish)
    property var moods: ({})                // address -> {m, until}; "_drag" is the dragged blob
    property var geo: ({})                  // address -> {x, y, w, h, visible}, in this overlay's own pixels
    // Several monitors: the overlay covers the monitor you are using (the focused one) and follows you when you move to another. Positions are shifted by that
    // monitor's origin, and only windows on it show a goop (a goop stays with its window, it is just hidden while you are on the other screen).
    property string monName: ""
    property real monX: 0
    property real monY: 0
    property int monId: 0
    property var spots: computeSpots()      // [{addr, x, y, vis}] top-center of each goop window
    property real cx: width / 2             // cursor position, for gaze
    property real cy: height / 2

    // drag state: the dragged blob is (bx, by); srcAddr is the goop it was peeled from
    property bool dragging: false
    property bool settling: false           // blob is gliding to a target or springing back
    property string srcAddr: ""
    property real bx: 0
    property real by: 0
    property string dragColor: "#e5484d"    // color/seed the blob keeps when it lands
    property int dragSeed: 0
    property real popScale: 1
    // --- animation level, from ~/.config/goop/config.json (watched: `goopctl animations off` applies instantly) ---
    //   full: liquid wobble, jelly breathing, drips   reduced: plain round goops, blinking and gaze   off: static, no cursor tracking
    property string animations: "full"
    // the master switch (config `enabled`, the panel's Turn off button, `goopctl off`): off hides the goops and stops every helper process
    property bool gooEnabled: true
    onGooEnabledChanged: if (!gooEnabled) {
        stopSpeech(); askAddr = ""; chooseAddr = ""; wizardOpen = false;
        ttsReady = false; sttWanted = false; sttReady = false; sttWantListen = false;
    }
    readonly property bool animLive: animations === "full"
    readonly property bool animEyes: animations !== "off"
    property bool cfgMissing: false
    // the first-run setup card (Wizard.qml): opens by itself once, as soon as a goop exists and the config says setup has not been done
    property int setupVersion: 0
    property bool configLoaded: false
    property bool wizardOpen: false
    property bool wizardShown: false
    readonly property bool wantWizard: gooEnabled && configLoaded && setupVersion < 1 && perched.length > 0
    onWantWizardChanged: if (wantWizard && !wizardShown) { wizardShown = true; wizardOpen = true; }
    function reloadVoice() {          // after setup installed the voice: start the voice and microphone processes again so they find it
        ttsReady = false; tts.running = false; voiceRestart.start();
        sttWanted = false; sttReady = false; sttWantListen = false;
    }
    Timer { id: voiceRestart; interval: 500; onTriggered: tts.running = true }
    property string provider: "claude"
    property string explainers: "offer"    // 3D lessons: offer (a card asks first) | auto | never (enforced in the daemon)
    property string access: "ask"          // look | ask | ask_all (enforced in the daemon; shown in the settings panel)
    function setMuted(on) {
        muted = on;
        if (ttsReady) tts.write(JSON.stringify({ cmd: "mute", on: on }) + "\n");
    }
    function applyConfig(t) {
        try {
            var c = JSON.parse(t), a = c.animations;
            animations = (a === "reduced" || a === "off") ? a : "full";
            gooEnabled = c.enabled !== false;
            provider = c.provider || "claude";
            setupVersion = c.setup_version || 0;
            configLoaded = true;
            if (setupVersion >= 1) { wizardOpen = false; wizardShown = false; }         // finished: it may open again when the panel resets setup_version to 0
            access = (c.access === "look" || c.access === "ask_all") ? c.access : "ask";
            explainers = (c.explainers === "auto" || c.explainers === "never") ? c.explainers : "offer";
            sttEnabled = !(c.stt && c.stt.enabled === false);
            sttAutoSend = (c.stt && c.stt.auto_send_ms !== undefined) ? c.stt.auto_send_ms : 1500;
            setMuted(!!(c.tts && c.tts.muted));      // muting from the panel (or goopctl) is saved, so it survives a restart
        } catch (e) { animations = "full"; }
    }
    FileView {
        id: userCfg
        path: Quickshell.env("HOME") + "/.config/goop/config.json"
        watchChanges: true
        printErrors: false                      // a missing file is normal until the user changes a setting
        onFileChanged: reload()
        onLoaded: { win.cfgMissing = false; win.applyConfig(text()); }
        onLoadFailed: { win.cfgMissing = true; win.animations = "full"; win.configLoaded = true; }     // no config file yet: defaults
    }
    Timer { interval: 3000; repeat: true; running: win.cfgMissing; onTriggered: userCfg.reload() }
    signal dripNow()

    property real gooT: 0                   // seconds; drives the liquid wobble of every goop
    readonly property real gooT0: Date.now()
    function computeAnyVisible() { for (var i = 0; i < spots.length; i++) if (spots[i].vis) return true; return false; }
    readonly property bool anyVisible: computeAnyVisible()
    // 30 fps is plenty for a slow wobble, and it only runs while a goop is on screen
    Timer { interval: 33; repeat: true; running: (win.anyVisible || win.dragging) && win.animLive; onTriggered: win.gooT = (Date.now() - win.gooT0) / 1000 }
    property bool ttsReady: false
    property bool muted: false
    property string speakingAddr: ""        // the goop whose mouth is moving
    property real level: 0                  // current loudness 0..1 from the voice process
    property real levelS: level             // smoothed, drives the mouth bar
    Behavior on levelS { NumberAnimation { duration: 60 } }
    property string askAddr: ""             // goop whose ask box is open
    // voice input (daemon/stt_server.py): the speech model loads when the first ask box opens, then stays warm; the microphone itself is only open while listening
    property bool sttEnabled: true
    property bool sttWanted: false
    property bool sttReady: false
    property bool sttWantListen: false      // asked to listen before the model finished loading
    property string sttState: "idle"        // idle | listening | off (the speech process said it is not available)
    property string chooseAddr: ""          // goop whose Talk / Type buttons are showing
    property real sttLevel: 0
    property int sttAutoSend: 1500          // ms the heard text stays on screen before it is sent (0 = wait for Enter)
    signal sttPartial(string text)
    signal sttFinal(string text)
    // the speech model is big (about 400 MB while loaded), so it is let go a few minutes after the last ask box; the next one reloads it in a second or two
    Timer { id: sttIdle; interval: 180000; onTriggered: { win.sttWanted = false; win.sttReady = false; win.sttWantListen = false; } }
    onAskAddrChanged: if (askAddr === "" && chooseAddr === "") sttIdle.restart()
    onChooseAddrChanged: if (askAddr === "" && chooseAddr === "") sttIdle.restart()
    function sttWrite(o) { if (sttReady) stt.write(JSON.stringify(o) + "\n"); }
    function startListening() {
        sttIdle.stop();
        if (!sttEnabled) return;
        sttWanted = true;
        if (sttReady) { sttWantListen = false; sttWrite({ cmd: "listen", address: askAddr }); } else sttWantListen = true;
    }
    function stopListening() { sttWantListen = false; sttWrite({ cmd: "stop" }); }       // finish now: whatever was heard becomes the question
    function cancelListening() { sttWantListen = false; sttWrite({ cmd: "cancel" }); }
    function sttEvent(line) {
        var e;
        try { e = JSON.parse(line); } catch (x) { return; }
        if (e.type === "ready") { sttReady = true; sttState = "idle"; if (sttWantListen) startListening(); }
        else if (e.type === "unavailable" || e.type === "disabled") {
            sttReady = false; sttState = "off"; sttWantListen = false; console.log("GOOP stt:", e.type, e.why || "");
            if (chooseAddr !== "") { var a = chooseAddr; chooseAddr = ""; askAddr = a; }      // no microphone: go straight to typing
        }
        else if (e.type === "listening") sttState = "listening";
        else if (e.type === "level") sttLevel = e.v;
        else if (e.type === "partial") sttPartial(e.text);
        else if (e.type === "final") sttFinal(e.text);
        else if (e.type === "idle") { sttState = "idle"; sttLevel = 0; }
        else if (e.type === "error") { sttState = "idle"; sttLevel = 0; console.log("GOOP stt error:", e.why); }
    }
    property var approvals: []              // actions waiting for the user's Approve/Deny (from the daemon)
    property var answered: ({})             // ids already answered, so a stale poll cannot bring a card back
    readonly property var approval: firstApproval()
    function firstApproval() {
        for (var i = 0; i < approvals.length; i++) {
            var sp = spotOf(approvals[i].address);
            if (sp && sp.vis && !answered[approvals[i].id]) return approvals[i];
        }
        return null;
    }
    function answerApproval(id, yes) {
        var a = {};
        for (var k in answered) a[k] = true;
        a[id] = true;
        answered = a;
        answerProc.command = ["python3", root.daemon + "/answer.py", id, yes ? "yes" : "no"];
        answerProc.running = true;
    }
    signal ask(string addr, string text)    // delegates listen and run the agent
    // clicking a goop offers Talk and Type, one on each side of it; with no microphone it goes straight to the typing box
    function clickGoop(addr) {
        stopSpeech();
        if (chooseAddr === addr) { chooseAddr = ""; return; }
        if (sttEnabled && sttState !== "off") { chooseAddr = addr; askAddr = ""; sttWanted = true; sttIdle.stop(); }    // the speech model loads while they decide
        else openAsk(addr, false);
    }
    function openAsk(addr, voice) {
        chooseAddr = ""; stopSpeech(); askAddr = addr;
        if (voice) startListening();
    }
    function speak(addr, text) {
        if (!ttsReady || muted || !text) return;
        tts.write(JSON.stringify({ cmd: "speak", id: addr, text: text, seed: seedOf(addr) }) + "\n");
    }
    function stopSpeech() { if (ttsReady) tts.write('{"cmd":"stop"}\n'); }
    function ttsEvent(line) {
        var e;
        try { e = JSON.parse(line); } catch (x) { return; }
        if (e.type === "ready") { ttsReady = true; if (muted) tts.write('{"cmd":"mute","on":true}\n'); }
        else if (e.type === "start") speakingAddr = e.id;
        else if (e.type === "level") { if (e.id === speakingAddr) level = e.v; }
        else if (e.type === "end") { if (speakingAddr === e.id) { speakingAddr = ""; level = 0; } }
    }
    function submitAsk(t) {
        var a = askAddr, q = t.trim();
        askAddr = "";
        cancelListening();
        if (q !== "") ask(a, q);
    }
    property string landAddr: ""
    property real landX: 0
    property real landY: 0

    function tidy(t, max) {
        if (t.length <= max) return t;
        var head = t.substring(0, max), cut = Math.max(head.lastIndexOf(". "), head.lastIndexOf("! "), head.lastIndexOf("? "));
        return (cut > max * 0.4 ? head.substring(0, cut + 1) : head.substring(0, head.lastIndexOf(" "))) + " ...";
    }
    // A reply that ends in a question gets quick-reply buttons. "Keep going / Enough" when it is offering more, else "Yes / No thanks".
    function offerFor(t) {
        var body = (t || "").trim().replace(/["')\]\s]+$/, "");
        if (body.charAt(body.length - 1) !== "?") return null;
        var head = body.substring(0, body.length - 1);
        var cut = Math.max(head.lastIndexOf(". "), head.lastIndexOf("! "), head.lastIndexOf("? "));
        var q = body.substring(cut + 1);
        if (/\b(keep going|continue|go on|more|go through|walk through|next)\b/i.test(q))
            return { yes: "Keep going", no: "Enough", reply: "Yes, keep going." };
        return { yes: "Yes", no: "No thanks", reply: "Yes." };
    }
    property var chipRects: ({})            // address -> {x, y, w, h} of that goop's visible buttons (so only they take clicks)
    function setChipRect(addr, r) {
        var c = {};
        for (var k in chipRects) c[k] = chipRects[k];
        if (r) c[addr] = r; else delete c[addr];
        chipRects = c;
    }
    function chipSlot(i) { var k = Object.keys(chipRects); return i < k.length ? chipRects[k[i]] : null; }
    signal injectReply(string addr, string text)   // test hooks (IPC): show a reply / press a button without the agent or a mouse
    signal offerAnswered(string addr, bool yes)
    function colorOf(addr) { return colors[addr] || palette[0]; }
    function seedOf(addr) { return seeds[addr] !== undefined ? seeds[addr] : 0; }
    function moodOf(addr) { return moods[addr] ? moods[addr].m : "idle"; }
    // temporary mood; falls back to idle after ms (this is the hook the Claude integration will drive)
    function setMood(addr, m, ms) {
        var c = {};
        for (var k in moods) c[k] = moods[k];
        c[addr] = { m: m, until: Date.now() + ms };
        moods = c;
    }
    function expireMoods() {
        var now = Date.now(), c = {}, changed = false;
        for (var k in moods) { if (moods[k].until > now) c[k] = moods[k]; else changed = true; }
        if (changed) moods = c;
    }
    // a copy never reuses a color that another goop is wearing
    function nextColor() {
        var used = {};
        for (var i = 0; i < perched.length; i++) used[colorOf(perched[i])] = true;
        for (var j = 0; j < palette.length; j++) if (!used[palette[j]]) return palette[j];
        return palette[perched.length % palette.length];
    }
    function gaze(dx, dy, axis) {
        var len = Math.hypot(dx, dy);
        if (len < 1) return 0;
        var k = Math.min(1, len / 220);
        return (axis === 0 ? dx : dy) / len * k;
    }
    function computeSpots() {
        var out = [];
        for (var i = 0; i < perched.length; i++) {
            var g = geo[perched[i]];
            out.push({ addr: perched[i], x: g ? g.x + g.w / 2 : 0, y: g ? g.y : 0, vis: !!g && g.visible });
        }
        return out;
    }
    function spotOf(addr) {
        for (var i = 0; i < spots.length; i++) if (spots[i].addr === addr) return spots[i];
        return null;
    }
    readonly property var srcSpot: spotOf(srcAddr)
    readonly property real sx: srcSpot ? srcSpot.x : 0
    readonly property real sy: srcSpot ? srcSpot.y : 0
    readonly property real dist: Math.hypot(bx - sx, by - sy)
    readonly property bool srcVisible: !!srcSpot && srcSpot.vis
    readonly property real srcR: Math.max(6, r - dist * 0.035)   // source gives goo up as you pull

    // Input: only the goops take clicks; while dragging, the whole surface does.
    mask: Region {
        item: win.dragging ? full : none
        Region { item: card }
        Region { item: slot0 }
        Region { item: slot1 }
        Region { item: slot2 }
        Region { item: slot3 }
        Region { item: slot4 }
        Region { item: slot5 }
        Region { item: slot6 }
        Region { item: slot7 }
        Region { item: chip0 }
        Region { item: chip1 }
        Region { item: chip2 }
        Region { item: chip3 }
        Region { item: chip4 }
        Region { item: chip5 }
        Region { item: chip6 }
        Region { item: chip7 }
    }
    Item { id: full; anchors.fill: parent }
    Item { id: none; width: 0; height: 0 }
    Item { id: slot0; x: win.spots.length > 0 ? win.spots[0].x - 18 : 0; y: win.spots.length > 0 ? win.spots[0].y - 18 : 0; width: win.spots.length > 0 && win.spots[0].vis ? 36 : 0; height: width }
    Item { id: slot1; x: win.spots.length > 1 ? win.spots[1].x - 18 : 0; y: win.spots.length > 1 ? win.spots[1].y - 18 : 0; width: win.spots.length > 1 && win.spots[1].vis ? 36 : 0; height: width }
    Item { id: slot2; x: win.spots.length > 2 ? win.spots[2].x - 18 : 0; y: win.spots.length > 2 ? win.spots[2].y - 18 : 0; width: win.spots.length > 2 && win.spots[2].vis ? 36 : 0; height: width }
    Item { id: slot3; x: win.spots.length > 3 ? win.spots[3].x - 18 : 0; y: win.spots.length > 3 ? win.spots[3].y - 18 : 0; width: win.spots.length > 3 && win.spots[3].vis ? 36 : 0; height: width }
    Item { id: slot4; x: win.spots.length > 4 ? win.spots[4].x - 18 : 0; y: win.spots.length > 4 ? win.spots[4].y - 18 : 0; width: win.spots.length > 4 && win.spots[4].vis ? 36 : 0; height: width }
    Item { id: slot5; x: win.spots.length > 5 ? win.spots[5].x - 18 : 0; y: win.spots.length > 5 ? win.spots[5].y - 18 : 0; width: win.spots.length > 5 && win.spots[5].vis ? 36 : 0; height: width }
    Item { id: slot6; x: win.spots.length > 6 ? win.spots[6].x - 18 : 0; y: win.spots.length > 6 ? win.spots[6].y - 18 : 0; width: win.spots.length > 6 && win.spots[6].vis ? 36 : 0; height: width }
    Item { id: slot7; x: win.spots.length > 7 ? win.spots[7].x - 18 : 0; y: win.spots.length > 7 ? win.spots[7].y - 18 : 0; width: win.spots.length > 7 && win.spots[7].vis ? 36 : 0; height: width }
    Item { id: chip0; property var r: win.chipSlot(0); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip1; property var r: win.chipSlot(1); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip2; property var r: win.chipSlot(2); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip3; property var r: win.chipSlot(3); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip4; property var r: win.chipSlot(4); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip5; property var r: win.chipSlot(5); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip6; property var r: win.chipSlot(6); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }
    Item { id: chip7; property var r: win.chipSlot(7); x: r ? r.x : 0; y: r ? r.y : 0; width: r ? r.w : 0; height: r ? r.h : 0 }

    // --- window state: where windows are, and seed the first goop ---
    Process {
        id: state
        command: ["python3", root.daemon + "/state.py"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var s = JSON.parse(text), g = {}, first = null, mons = s.monitors || [], cur = null;
                    for (var m = 0; m < mons.length; m++) if (mons[m].focused) cur = mons[m];
                    if (!cur && mons.length) cur = mons[0];
                    if (cur) { win.monName = cur.name; win.monX = cur.x; win.monY = cur.y; win.monId = cur.id; }
                    for (var i = 0; i < s.windows.length; i++) {
                        var w = s.windows[i];
                        w.visible = w.visible && (!cur || w.monitor === cur.id);                 // only windows on this monitor show a goop now
                        w.x -= win.monX; w.y -= win.monY;
                        g[w.address] = w;
                        if (!first && w.visible) first = w.address;
                    }
                    win.geo = g;
                    win.approvals = s.approvals || [];
                    // a closed window takes its goop with it (never mid-drag)
                    if (!win.dragging && !win.settling) {
                        var kept = win.perched.filter(function (a) { return g[a] !== undefined; });
                        if (kept.length !== win.perched.length) win.perched = kept;     // only when a window actually closed
                    }
                    // no goop anywhere: the first active window gets one
                    if (win.perched.length === 0 && !win.dragging && !win.settling) {
                        var seed = (s.active && g[s.active] && g[s.active].visible) ? s.active : first;
                        if (seed) {
                            var c = {}; c[seed] = win.palette[0];
                            var sd = {}; sd[seed] = Math.floor(Math.random() * 100000);
                            win.colors = c;
                            win.seeds = sd;
                            win.perched = [seed];
                        }
                    }
                } catch (e) {}
            }
        }
    }
    Timer {
        interval: 250; running: win.gooEnabled; repeat: true
        onTriggered: { win.expireMoods(); if (!state.running) state.running = true }
    }

    // --- the goops' voice: Piper, on-device, kept warm. Missing venv/model just means silence. ---
    Process {
        id: tts
        running: win.gooEnabled
        stdinEnabled: true
        command: [root.venvPython, root.daemon + "/tts_server.py"]
        stdout: SplitParser { onRead: line => win.ttsEvent(line) }
        stderr: StdioCollector { onStreamFinished: if (text) console.log("TTS-ERR:", text) }
    }

    // --- the goops' ears: Moonshine, on-device. Loads on the first ask box; missing venv/model just means no microphone button. ---
    Process {
        id: stt
        running: win.gooEnabled && win.sttEnabled && win.sttWanted
        stdinEnabled: true
        command: [root.venvPython, root.daemon + "/stt_server.py"]
        stdout: SplitParser { onRead: line => win.sttEvent(line) }
        stderr: StdioCollector { onStreamFinished: if (text) console.log("STT-ERR:", text) }
    }

    // --- cursor feed for gaze (only while a goop exists) ---
    Process {
        running: win.gooEnabled && win.perched.length > 0 && win.animEyes
        command: ["python3", root.daemon + "/cursor.py"]
        stdout: SplitParser {
            onRead: line => {
                var p = line.split(" ");
                if (p.length === 2) { win.cx = parseFloat(p[0]) - win.monX; win.cy = parseFloat(p[1]) - win.monY; }
            }
        }
    }

    Process { id: answerProc }

    // --- approval card: shows the exact action; nothing happens until Approve ---
    Item {
        id: card
        readonly property var a: win.approval
        readonly property var spot: a ? win.spotOf(a.address) : null
        readonly property color accent: a ? win.colorOf(a.address) : "#888"
        readonly property real cardW: 290
        visible: !!a
        width: a ? cardW : 0
        height: a ? col.implicitHeight + 22 : 0
        x: spot ? Math.max(8, Math.min(win.width - cardW - 8, spot.x - cardW / 2)) : 0
        y: spot ? spot.y + 26 : 0
        Rectangle {
            anchors.fill: parent
            radius: 12
            color: "#f2161619"
            border.width: 1
            border.color: Qt.alpha(card.accent, 0.7)
        }
        Column {
            id: col
            x: 12; y: 11
            width: parent.width - 24
            spacing: 8
            Text {
                width: parent.width
                text: card.a ? card.a.summary : ""
                color: "#b9b9c2"; font.pixelSize: 12
                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            }
            Rectangle {
                visible: !!card.a && card.a.detail !== ""
                width: parent.width
                height: visible ? detail.implicitHeight + 12 : 0
                radius: 6
                color: "#1fffffff"
                Text {
                    id: detail
                    x: 8; y: 6; width: parent.width - 16
                    text: card.a ? card.a.detail : ""
                    color: "#f0f0f0"; font.family: "monospace"; font.pixelSize: 12
                    wrapMode: Text.WrapAnywhere; maximumLineCount: 12; elide: Text.ElideRight
                }
            }
            Row {
                spacing: 6
                layoutDirection: Qt.RightToLeft     // buttons sit on the right, Approve outermost
                width: parent.width
                Rectangle {
                    width: approveLabel.implicitWidth + 24; height: 24; radius: 12
                    color: approveMa.containsMouse ? Qt.lighter(card.accent, 1.15) : card.accent
                    Text { id: approveLabel; anchors.centerIn: parent; text: "Approve"; color: "white"; font.pixelSize: 12; font.bold: true }
                    MouseArea { id: approveMa; anchors.fill: parent; hoverEnabled: true; onClicked: win.answerApproval(card.a.id, true) }
                }
                Rectangle {
                    width: denyLabel.implicitWidth + 24; height: 24; radius: 12
                    color: denyMa.containsMouse ? "#2c2c33" : "transparent"
                    border.width: 1; border.color: "#44444c"
                    Text { id: denyLabel; anchors.centerIn: parent; text: "Deny"; color: "#d0d0d6"; font.pixelSize: 12 }
                    MouseArea { id: denyMa; anchors.fill: parent; hoverEnabled: true; onClicked: win.answerApproval(card.a.id, false) }
                }
            }
        }
    }

    // --- resting goops ---
    Repeater {
        model: win.perched
        delegate: Item {
            id: gp
            property var spot: win.spotOf(modelData)
            property int seed: win.seedOf(modelData)
            property real phase: 0
            property string bubble: ""          // what this goop is saying
            property string sessionId: ""       // resume token, so follow-ups keep context
            property bool busy: false
            property var offer: null            // quick replies shown under the bubble, or null
            // how agitated this goop is: speaking, thinking and surprise make the liquid wobble more
            readonly property real energy: Math.max(win.speakingAddr === modelData ? 0.45 + win.levelS * 0.9 : 0,
                ({ thinking: 0.55, startled: 0.9, happy: 0.4, error: 0.3 })[win.moodOf(modelData)] || 0)
            property real energyS: energy
            Behavior on energyS { NumberAnimation { duration: 300 } }
            readonly property var chipGeo: chips.visible ? ({ x: gp.x + chips.x, y: gp.y + chips.y, w: chips.width, h: chips.height }) : null
            onChipGeoChanged: win.setChipRect(modelData, chipGeo)
            Component.onDestruction: win.setChipRect(modelData, null)
            readonly property real squish: (Math.floor(seed / 2) % 5 - 2) * 0.025   // each goop is a touch wider or taller
            // the drag source must stay visible mid-drag: hiding an item cancels its mouse grab, which would kill a
            // peel that crosses to another workspace
            visible: (!!spot && spot.vis) || (modelData === win.srcAddr && (win.dragging || win.settling))
            x: spot ? spot.x - win.r : 0
            y: spot ? spot.y - win.r : 0
            width: win.r * 2; height: width
            opacity: (modelData === win.srcAddr && (win.dragging || win.settling)) ? 0 : 1
            Behavior on x { NumberAnimation { duration: 120 } }
            Behavior on y { NumberAnimation { duration: 120 } }
            NumberAnimation on phase {
                from: gp.seed % 6; to: gp.seed % 6 + 6.2832
                duration: 3200 + (gp.seed % 7) * 180
                loops: Animation.Infinite
                running: gp.visible && win.animLive
            }

            // --- talking to the agent ---
            function run(t) {
                if (busy) { bubble = "still thinking..."; return; }
                if (win.speakingAddr === modelData) win.stopSpeech();
                busy = true;
                offer = null;
                fade.stop();
                bubble = "...";
                win.setMood(modelData, "thinking", 600000);
                var cmd = ["python3", root.daemon + "/agent.py", "--address", modelData, "--command", t];
                if (sessionId) cmd = cmd.concat(["--session", sessionId]);
                agent.command = cmd;
                agent.running = true;
            }
            function showReply(t) {
                busy = false;
                bubble = win.tidy(t, 900);
                offer = win.offerFor(t);
                win.setMood(modelData, "happy", 2500);
                win.speak(modelData, bubble);
                fade.interval = Math.max(offer ? 30000 : 0, 8000 + bubble.length * 60);   // buttons get time: you may be listening first
                fade.restart();
            }
            function answerOffer(yes) {
                var o = offer;
                offer = null;
                if (!o) return;
                if (yes) {
                    win.ask(modelData, o.reply);                 // same path as typing it
                } else {
                    fade.stop();
                    bubble = "";
                    if (win.speakingAddr === modelData) win.stopSpeech();
                }
            }
            function fail(msg) {
                busy = false;
                bubble = "oops: " + msg;
                win.setMood(modelData, "error", 4000);
                fade.interval = 8000; fade.restart();
            }
            function handleEvent(line) {
                var e;
                try { e = JSON.parse(line); } catch (x) { return; }
                if (e.type === "start" || e.type === "thinking") {
                    win.setMood(modelData, "thinking", 600000);
                } else if (e.type === "tool_use") {
                    bubble = (e.name === "type_in_terminal" || e.name === "move_files" || e.name === "undo_last_move")
                        ? "waiting for your OK..." : "looking (" + e.name + ")...";
                } else if (e.type === "text") {
                    bubble = win.tidy(e.text, 900);
                } else if (e.type === "done") {
                    busy = false;
                    if (e.session) sessionId = e.session;
                    showReply(e.text || "done");
                } else if (e.type === "error") {
                    fail(e.message);
                }
            }
            Process {
                id: agent
                stdout: SplitParser { onRead: line => gp.handleEvent(line) }
                stderr: StdioCollector { onStreamFinished: if (text) console.log("AGENT-ERR:", text) }
                onExited: (code) => { if (gp.busy) gp.fail("the agent stopped unexpectedly"); }
            }
            Timer { id: fade; onTriggered: { gp.bubble = ""; gp.offer = null } }
            Connections {
                target: win
                function onAsk(addr, text) { if (addr === modelData) gp.run(text); }
                function onInjectReply(addr, text) { if (addr === modelData) gp.showReply(text); }
                function onOfferAnswered(addr, yes) { if (addr === modelData) gp.answerOffer(yes); }
            }

            // --- drips (full animations only), drawn first so the goop overlaps where they join ---
            Loader {
                id: dripLoader
                x: gp.width / 2; y: gp.height - 1
                active: win.animLive && gp.visible
                sourceComponent: Component {
                    Drip {
                        color: win.colorOf(modelData)
                        calm: win.speakingAddr === modelData ? 2.5 : (win.moodOf(modelData) === "thinking" ? 0.5 : 1)
                    }
                }
            }
            Connections { target: win; function onDripNow() { if (dripLoader.item) dripLoader.item.trigger() } }

            // --- body ---
            Item {
                anchors.fill: parent
                // breathing as jelly: wider-and-shorter then taller-and-narrower, so the volume stays about the same
                transform: Scale {
                    origin.x: win.r; origin.y: win.r
                    xScale: win.animLive ? 1 + 0.05 * Math.sin(gp.phase) : 1
                    yScale: win.animLive ? 1 - 0.05 * Math.sin(gp.phase) + 0.015 * Math.sin(gp.phase * 2) : 1
                }
                GooBody {
                    anchors.centerIn: parent
                    r: win.r; seed: gp.seed; squish: gp.squish; energy: gp.energyS; t: win.gooT; live: win.animLive
                    color: win.colorOf(modelData)
                }
                Eyes {
                    x: win.r; y: win.r
                    seed: gp.seed
                    mood: win.moodOf(modelData)
                    alive: win.animEyes
                    gx: (win.animEyes && gp.spot) ? win.gaze(win.cx - gp.spot.x, win.cy - gp.spot.y, 0) : 0
                    gy: (win.animEyes && gp.spot) ? win.gaze(win.cx - gp.spot.x, win.cy - gp.spot.y, 1) : 0
                }
                Item {   // mouth: five little bars that dance with the voice; nothing else on the goop moves
                    id: mouth
                    x: win.r; y: win.r + 8
                    opacity: win.speakingAddr === modelData ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 110 } }
                    property real t: 0
                    NumberAnimation on t { from: 0; to: 6.2832; duration: 600; loops: Animation.Infinite; running: mouth.opacity > 0 }
                    Repeater {
                        model: 5
                        delegate: Rectangle {
                            readonly property real shape: [0.5, 0.8, 1, 0.8, 0.5][index]   // tallest in the middle, so it stays inside the face
                            width: 1.8; radius: 0.9; color: "white"
                            height: 1.6 + win.levelS * 6 * shape * (0.45 + 0.55 * Math.abs(Math.sin(mouth.t * 2 + index * 1.25)))
                            x: (index - 2) * 2.8 - 0.9
                            y: -height / 2
                        }
                    }
                }
            }

            // --- speech bubble (not clickable: pointer events pass through to the window below) ---
            Rectangle {
                id: bub
                visible: gp.bubble !== "" && win.askAddr !== modelData && !(win.approval && win.approval.address === modelData)
                // shrink-wraps a short reply; a long one gets a wider bubble that grows downward, capped to half the screen
                width: Math.min(win.width - 16, bubbleMeasure.implicitWidth + 22, gp.bubble.length > 120 ? 340 : 280)
                height: Math.min(txt.implicitHeight + 18, Math.max(120, win.height * 0.5))
                clip: true
                x: Math.max(8, Math.min(win.width - width - 8, gp.spot ? gp.spot.x - width / 2 : 0)) - gp.x
                y: gp.height + 8
                radius: 10
                color: "#f0151518"
                border.color: win.colorOf(modelData); border.width: 1.5
                Text { id: bubbleMeasure; visible: false; font.pixelSize: 13; text: gp.bubble; textFormat: Text.MarkdownText; wrapMode: Text.NoWrap }
                Text {
                    id: txt
                    x: 10; y: 9; width: parent.width - 20
                    text: gp.bubble
                    textFormat: Text.MarkdownText       // `code`, lists and bold render instead of showing raw symbols
                    color: "white"; font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
            }

            // --- quick replies: small, goop-colored, only while the reply ends in a question ---
            Row {
                id: chips
                visible: bub.visible && !!gp.offer && !win.dragging && !win.settling
                x: bub.x
                y: bub.y + bub.height + 6
                spacing: 6
                Rectangle {
                    width: yesLabel.implicitWidth + 22; height: 22; radius: 11
                    color: yesMa.containsMouse ? Qt.lighter(win.colorOf(modelData), 1.15) : win.colorOf(modelData)
                    Text { id: yesLabel; anchors.centerIn: parent; text: gp.offer ? gp.offer.yes : ""; color: "white"; font.pixelSize: 12; font.bold: true }
                    MouseArea { id: yesMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: gp.answerOffer(true) }
                }
                Rectangle {
                    width: noLabel.implicitWidth + 22; height: 22; radius: 11
                    color: noMa.containsMouse ? "#2c2c33" : "#e6151518"
                    border.width: 1; border.color: "#44444c"
                    Text { id: noLabel; anchors.centerIn: parent; text: gp.offer ? gp.offer.no : ""; color: "#d0d0d6"; font.pixelSize: 12 }
                    MouseArea { id: noMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: gp.answerOffer(false) }
                }
            }

            MouseArea {
                id: ma
                anchors.fill: parent
                cursorShape: Qt.OpenHandCursor
                preventStealing: true
                property real ox; property real oy
                onPressed: {
                    var p = ma.mapToItem(win.contentItem, 0, 0);
                    ox = p.x; oy = p.y;
                    win.srcAddr = modelData;
                    win.dragColor = win.nextColor();
                    win.dragSeed = Math.floor(Math.random() * 100000);
                    win.bx = win.sx; win.by = win.sy;
                    win.dragging = true;
                    win.setMood("_drag", "startled", 700);
                    pop.restart();
                }
                onPositionChanged: (m) => {
                    if (!win.dragging) return;
                    win.bx = ox + m.x;
                    win.by = oy + m.y;
                }
                onCanceled: {
                    if (win.dragging) { win.dragging = false; win.settling = true; back.start(); }
                }
                onReleased: {
                    if (win.dist < 6) {          // a click, not a peel: ask this goop something
                        win.dragging = false;
                        win.settling = false;
                        win.srcAddr = "";
                        win.clickGoop(modelData);
                        return;
                    }
                    win.dragging = false;
                    win.settling = true;
                    probe.running = true;
                }
            }
        }
    }

    // --- the stretchy peel: source blob, pinching neck, dragged blob ---
    Canvas {
        id: goo
        anchors.fill: parent
        visible: win.dragging || win.settling
        onPaint: {
            var c = getContext("2d");
            c.clearRect(0, 0, width, height);
            if (!(win.dragging || win.settling)) return;
            var sx = win.sx, sy = win.sy, x = win.bx, y = win.by, R = win.r * win.popScale;
            var dx = x - sx, dy = y - sy, d = win.dist;
            var a = Math.atan2(dy, dx), nx = -Math.sin(a), ny = Math.cos(a);
            var rs = win.srcR;
            var srcCol = win.colorOf(win.srcAddr);
            if (d > 2 && win.srcVisible) {
                // the neck pinches toward the middle as you pull and blends from the source's color into the new one
                var gr = c.createLinearGradient(sx, sy, x, y);
                gr.addColorStop(0, srcCol);
                gr.addColorStop(1, win.dragColor);
                c.fillStyle = gr;
                var wm = Math.max(1.2, rs * 0.55 * (1 - d / 230));
                var mx = (sx + x) / 2, my = (sy + y) / 2;
                var cw = Math.max(0.6, 2 * wm - (rs + R) / 2 * 0.5);
                c.beginPath();
                c.moveTo(sx + nx * rs, sy + ny * rs);
                c.quadraticCurveTo(mx + nx * cw, my + ny * cw, x + nx * R, y + ny * R);
                c.lineTo(x - nx * R, y - ny * R);
                c.quadraticCurveTo(mx - nx * cw, my - ny * cw, sx - nx * rs, sy - ny * rs);
                c.closePath();
                c.fill();
            }
            if (win.srcVisible) {
                c.fillStyle = srcCol;
                if (win.animLive) { Goo.draw(c, Goo.points(sx, sy, rs, win.gooT, win.seedOf(win.srcAddr), 0, 0.3)); }
                else { c.beginPath(); c.arc(sx, sy, rs, 0, Math.PI * 2); }
                c.fill();
            }
            c.fillStyle = win.dragColor;
            if (win.animLive) { Goo.draw(c, Goo.points(x, y, R, win.gooT + 1.7, win.dragSeed, 0, 0.9)); }   // the pulled blob is more agitated
            else { c.beginPath(); c.arc(x, y, R, 0, Math.PI * 2); }
            c.fill();
        }
    }
    Connections {
        target: win
        function onBxChanged() { goo.requestPaint() }
        function onByChanged() { goo.requestPaint() }
        function onPopScaleChanged() { goo.requestPaint() }
        function onDraggingChanged() { goo.requestPaint() }
        function onSettlingChanged() { goo.requestPaint() }
        function onSpotsChanged() { if (win.dragging || win.settling) goo.requestPaint() }
        function onSrcVisibleChanged() { goo.requestPaint() }
        function onGooTChanged() { if (win.dragging || win.settling) goo.requestPaint() }
    }
    // eyes of the two blobs while peeling: the source glances at the blob, the blob looks where it is heading
    Eyes {
        visible: (win.dragging || win.settling) && win.srcVisible
        x: win.sx; y: win.sy
        scale: win.srcR / win.r
        seed: win.seedOf(win.srcAddr)
        gx: win.dist > 2 ? (win.bx - win.sx) / win.dist * 0.9 : 0
        gy: win.dist > 2 ? (win.by - win.sy) / win.dist * 0.9 : 0
    }
    Eyes {
        visible: win.dragging || win.settling
        x: win.bx; y: win.by
        scale: win.popScale
        seed: win.dragSeed
        mood: win.moodOf("_drag")
        gx: win.dist > 2 ? (win.bx - win.sx) / win.dist * Math.min(1, win.dist / 60) : 0
        gy: win.dist > 2 ? (win.by - win.sy) / win.dist * Math.min(1, win.dist / 60) : 0
    }
    SequentialAnimation {
        id: pop
        NumberAnimation { target: win; property: "popScale"; to: 1.3; duration: 90 }
        NumberAnimation { target: win; property: "popScale"; to: 1; duration: 240; easing.type: Easing.OutBack }
    }

    // spring back to the source goop
    ParallelAnimation {
        id: back
        NumberAnimation { target: win; property: "bx"; to: win.sx; duration: 450; easing.type: Easing.OutElastic }
        NumberAnimation { target: win; property: "by"; to: win.sy; duration: 450; easing.type: Easing.OutElastic }
        onFinished: { win.settling = false; win.srcAddr = "" }
    }
    // glide into the target window and become its goop
    ParallelAnimation {
        id: land
        NumberAnimation { target: win; property: "bx"; to: win.landX; duration: 260; easing.type: Easing.OutCubic }
        NumberAnimation { target: win; property: "by"; to: win.landY; duration: 260; easing.type: Easing.OutCubic }
        onFinished: {
            var c = {}, s = {};
            for (var k in win.colors) c[k] = win.colors[k];
            for (var j in win.seeds) s[j] = win.seeds[j];
            c[win.landAddr] = win.dragColor;
            s[win.landAddr] = win.dragSeed;
            win.colors = c;
            win.seeds = s;
            win.perched = win.perched.concat([win.landAddr]);
            win.settling = false;
            win.srcAddr = "";
        }
    }

    Process {
        id: probe
        command: ["python3", root.daemon + "/drop.py"]
        stderr: StdioCollector { onStreamFinished: if (text) console.log("DROP-ERR:", text) }
        stdout: StdioCollector {
            onStreamFinished: {
                console.log("DROP:", text);
                var d = {};
                try { d = JSON.parse(text); } catch (e) {}
                var g = d.address ? win.geo[d.address] : null;
                if (g && win.perched.indexOf(d.address) < 0 && win.perched.length < win.maxGoops) {
                    win.landAddr = d.address;
                    win.landX = g.x + g.w / 2;
                    win.landY = g.y;
                    land.start();
                } else {
                    back.start();
                }
            }
        }
    }

    // test hooks (bin/goopctl wraps these): goopctl mood happy 3000 | goopctl list | goopctl say <addr> "..."
    IpcHandler {
        target: "goop"
        function list(): string { return win.perched.join("\n"); }
        function say(addr: string, text: string): void { win.ask(addr, text); }
        function speak(addr: string, text: string): void { win.speak(addr, text); }
        function mute(on: bool): void { win.setMuted(on); root.setSetting("tts.muted", on ? "true" : "false"); }
        function hush(): void { win.stopSpeech(); }
        function drip(): void { if (win.gooEnabled) win.dripNow(); }
        function explain(name: string): void { explainer.play(); }
        function explainStop(): void { explainer.stop(); }
        // The 3D version runs as its own program: a failure inside Qt Quick 3D must never be able to take down the shell (it once did).
        function explain3d(name: string): void { Quickshell.execDetached([root.here + "/../bin/goop-explain", name]); }
        function reply(addr: string, text: string): void { win.injectReply(addr, text); }
        function answer(addr: string, yes: bool): void { win.offerAnswered(addr, yes); }
        function openAsk(addr: string): void { win.openAsk(addr, false); }          // the typing box
        function listenAsk(addr: string): void { win.openAsk(addr, true); }         // the typing box, already listening
        function chooseAsk(addr: string): void { win.clickGoop(addr); }             // what a click does: the Talk / Type buttons
        function closeAsk(): void { win.askAddr = ""; win.chooseAddr = ""; }
        // the peel without a mouse (filming, tests): dragBegin <addr>, dragTo <x> <y> as often as you like, then dragEnd lands it under the real cursor
        function dragBegin(addr: string): void {
            if (win.dragging || win.perched.indexOf(addr) < 0) return;
            win.srcAddr = addr;
            win.dragColor = win.nextColor();
            win.dragSeed = Math.floor(Math.random() * 100000);
            win.bx = win.sx; win.by = win.sy;
            win.dragging = true;
            win.setMood("_drag", "startled", 700);
            pop.restart();
        }
        function dragTo(x: real, y: real): void { if (win.dragging) { win.bx = x; win.by = y; } }
        function dragEnd(): void { if (win.dragging) { win.dragging = false; win.settling = true; probe.running = true; } }
        function wizardStep(n: int): void { wizardWin.step = n; if (n === 1) wizardWin.refresh(); }     // jump to a step (for testing)
        function wizard(open: bool): void { win.wizardOpen = open; }
        function perch(addr: string): void {                                          // put a goop on a window (testing, and `goopctl perch`)
            if (win.perched.indexOf(addr) >= 0) return;
            var c = {}, sd = {};
            for (var k in win.colors) c[k] = win.colors[k];
            for (var j in win.seeds) sd[j] = win.seeds[j];
            c[addr] = win.nextColor(); sd[addr] = Math.floor(Math.random() * 100000);
            win.colors = c; win.seeds = sd; win.perched = win.perched.concat([addr]);
        }                    // show or hide the first-run setup card
        function askOpen(): string { return win.askAddr; }
        function mood(m: string, ms: int): void {
            for (var i = 0; i < win.perched.length; i++) win.setMood(win.perched[i], m, ms);
        }
    }
}

PanelWindow {
    id: askWin
    screen: win.screen
    visible: win.askAddr !== "" || win.chooseAddr !== ""
    // Full-screen and transparent. With exclusive keyboard focus Hyprland treats this surface as a modal and sends it every
    // click, so a press anywhere outside the box (the MouseArea below) is how "click away" is detected. The surface never
    // changes size, so typing does not make the compositor reconfigure it (that caused the old flicker).
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    WlrLayershell.namespace: "goop-ask"
    readonly property var spot: win.spotOf(win.askAddr !== "" ? win.askAddr : win.chooseAddr)
    onVisibleChanged: {
        if (visible && win.askAddr !== "") { input.text = ""; input.partial = false; autoSend.stop(); input.forceActiveFocus(); idle.restart(); }
        else if (visible) choiceKeys.forceActiveFocus();
        else { idle.stop(); autoSend.stop(); win.cancelListening(); }         // closing the box always closes the microphone
    }
    Timer { id: idle; interval: 20000; onTriggered: win.askAddr = "" }
    Timer { id: choiceTimer; interval: 8000; running: win.chooseAddr !== ""; onTriggered: win.chooseAddr = "" }
    Connections { target: win; function onChooseAddrChanged() { if (win.chooseAddr !== "") { choiceTimer.restart(); choiceKeys.forceActiveFocus(); } } }
    Connections { target: win; function onAskAddrChanged() { if (win.askAddr !== "") { input.forceActiveFocus(); } } }
    // what was heard stays on screen for a moment, with a bar running down, so a mistake can be fixed before it is sent
    Timer { id: autoSend; interval: Math.max(1, win.sttAutoSend); onTriggered: win.submitAsk(input.text) }
    Connections {
        target: win
        function onSttPartial(t) { input.partial = true; input.text = t; idle.restart(); }
        function onSttFinal(t) {
            idle.restart();
            input.partial = false;
            if (t.trim() === "") return;
            input.text = t;
            if (win.sttAutoSend > 0) autoSend.restart();
        }
    }
    Text { id: measure; visible: false; font.pixelSize: 14; wrapMode: Text.NoWrap; text: input.text !== "" ? input.text : box.hint }

    MouseArea { anchors.fill: parent; onPressed: { win.askAddr = ""; win.chooseAddr = ""; } }   // click away

    Rectangle {
        id: box
        visible: win.askAddr !== ""
        readonly property bool voice: win.sttEnabled && win.sttState !== "off"
        readonly property bool listening: win.sttState === "listening"
        readonly property color accent: win.colorOf(win.askAddr)
        readonly property real pad: voice ? 42 : 12
        readonly property string hint: !voice ? "Ask this goop..."
                                     : listening ? "Listening... just talk"
                                     : !win.sttReady ? "Starting the microphone..."
                                     : "Type, or click the mic to talk"
        // shrink-wrapped, centred under the goop: compact for a few words, wider as you type, then wraps
        readonly property real maxW: 380
        width: Math.max(voice ? 250 : 150, Math.min(maxW, measure.implicitWidth + pad + 18))
        height: Math.max(36, Math.min(170, input.contentHeight + 20)) + (autoSend.running ? 20 : 0)
        x: askWin.spot ? Math.max(8, Math.min(askWin.width - width - 8, askWin.spot.x - width / 2)) : 8
        y: askWin.spot ? askWin.spot.y + 26 : 40
        radius: 12
        color: "#f2161619"
        border.width: 1
        border.color: Qt.alpha(accent, 0.8)
        Behavior on height { NumberAnimation { duration: 90 } }
        MouseArea { anchors.fill: parent }       // clicks on the box itself must not count as click-away
        TapHandler { onTapped: autoSend.stop() } // touching the box means "wait, let me edit": the countdown stops

        Item {      // the microphone button: pulses with your voice while it listens; click it to finish early, or to talk again
            id: mic
            visible: box.voice
            x: 8; y: 5; width: 28; height: 28
            Rectangle {
                anchors.centerIn: parent
                width: 24 + win.sttLevel * 12; height: width; radius: width / 2
                color: Qt.alpha(box.accent, 0.28)
                visible: box.listening
                Behavior on width { NumberAnimation { duration: 70 } }
            }
            Rectangle {
                anchors.centerIn: parent
                width: 24; height: 24; radius: 12
                color: box.listening ? box.accent : (micMa.containsMouse ? "#3a3a44" : "#2c2c33")
                MicGlyph { anchors.centerIn: parent; scale: 0.9 }
            }
            MouseArea {
                id: micMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    autoSend.stop();
                    if (box.listening) win.stopListening();
                    else { input.partial = false; win.startListening(); }
                }
            }
        }
        TextEdit {
            id: input
            property bool partial: false
            x: box.pad; y: 10
            width: parent.width - box.pad - 12
            color: partial ? "#c9caff" : "white"; font.pixelSize: 14
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            onTextChanged: idle.restart()
            Keys.onPressed: (e) => {
                if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !(e.modifiers & Qt.ShiftModifier)) {
                    win.submitAsk(text); e.accepted = true;      // Shift+Enter inserts a new line
                } else if (e.key === Qt.Key_Escape) {
                    win.askAddr = ""; e.accepted = true;
                } else if (e.text.length > 0 || e.key === Qt.Key_Backspace || e.key === Qt.Key_Delete) {
                    autoSend.stop();                              // typing means "I will do this one by hand": no countdown, no more listening
                    input.partial = false;
                    if (win.sttState === "listening") win.cancelListening();
                }
            }
            Text {
                visible: !input.text
                text: box.hint
                color: box.listening ? "#b9b9ff" : "#77777f"; font: input.font
            }
        }
        Item {      // the countdown: a bar running down under the words, with the way out spelled out
            visible: autoSend.running
            x: 12; y: parent.height - 22; width: parent.width - 24; height: 18
            property real remain: 1
            NumberAnimation on remain { running: autoSend.running; from: 1; to: 0; duration: Math.max(1, win.sttAutoSend) }
            Rectangle { y: 0; width: parent.width * parent.remain; height: 3; radius: 1.5; color: box.accent }
            Text { y: 5; text: "Sending...  click or type to edit"; color: "#8d8d96"; font.pixelSize: 11 }
        }
    }

    // clicking a goop shows two round buttons, one on each side of it: Talk (microphone) and Type (pencil). The microphone stays closed until Talk is chosen.
    Item {
        id: choice
        visible: win.chooseAddr !== ""
        readonly property color accent: win.colorOf(win.chooseAddr)
        readonly property real cx: askWin.spot ? askWin.spot.x : 0
        readonly property real cy: askWin.spot ? askWin.spot.y : 0
        Item { id: choiceKeys; focus: true; Keys.onPressed: (e) => {
            if (e.key === Qt.Key_Escape) win.chooseAddr = "";
            else if (e.key === Qt.Key_M || e.key === Qt.Key_V) win.openAsk(win.chooseAddr, true);
            else if (e.key === Qt.Key_T || e.key === Qt.Key_Return) win.openAsk(win.chooseAddr, false);
            e.accepted = true;
        } }
        Repeater {
            model: [{ k: "talk", dx: -1, label: "Talk" }, { k: "type", dx: 1, label: "Type" }]
            delegate: Item {
                id: btn
                required property var modelData
                width: 44; height: 58
                x: choice.cx + modelData.dx * 46 - width / 2
                y: choice.cy - 14
                opacity: choice.visible ? 1 : 0
                scale: choice.visible ? 1 : 0.5
                Behavior on opacity { NumberAnimation { duration: 140 } }
                Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
                Rectangle {
                    id: disc
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 38; height: 38; radius: 19
                    color: ma.containsMouse ? "#f23a3a44" : "#f2161619"
                    border.width: 1.5
                    border.color: Qt.alpha(choice.accent, ma.containsMouse ? 1 : 0.8)
                    Behavior on color { ColorAnimation { duration: 90 } }
                    MicGlyph { visible: btn.modelData.k === "talk"; anchors.centerIn: parent; scale: 1.1 }
                    PencilGlyph { visible: btn.modelData.k === "type"; anchors.centerIn: parent; scale: 1.1 }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 42
                    text: btn.modelData.label
                    color: "#e6e6ee"; font.pixelSize: 12; font.weight: Font.DemiBold
                    style: Text.Outline; styleColor: "#cc000000"
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: win.openAsk(win.chooseAddr, btn.modelData.k === "talk")
                }
            }
        }
    }
}

    Wizard { id: wizardWin; app: win; paths: root }      // the first-run setup card
}
