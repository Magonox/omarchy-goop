import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Goop's settings, in the bar: a button that opens a popup with the animation level, voice, agent and a setup checklist.
// Everything it changes goes through ~/.config/goop/config.json (via daemon/settings.py), which the overlay watches, so
// changes apply instantly. It shows only while the plugin is enabled, i.e. whenever goop runs.
Panel {
  id: root
  moduleName: "shawn.goop"
  ipcTarget: "shawn.goop"

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(fg, 1.5)
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // where the plugin lives (plain paths: used for scripts, not for QML imports)
  readonly property string pluginDir: Qt.resolvedUrl("GoopPanel.qml").toString().replace("file://", "").replace(/\/[^\/]*$/, "") + "/.."

  // live state, published by the overlay (see Goop.qml) to a file the panel watches
  property var st: ({ goops: 0, voiceReady: false, muted: false, animations: "full", provider: "claude" })
  FileView {
    path: Quickshell.env("HOME") + "/.cache/goop/status.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { try { root.st = JSON.parse(text()) } catch (e) {} }
  }

  property var checks: []
  property var providers: []
  readonly property var problems: checks.filter(function(c) { return !c.ok })
  readonly property bool voiceMissing: checks.some(function(c) { return c.id === "voice" && !c.ok })
  readonly property var activeProvider: {
    for (var i = 0; i < providers.length; i++) if (providers[i].active) return providers[i]
    return null
  }
  readonly property string summary: st.goops + (st.goops === 1 ? " goop" : " goops")
    + " · " + (!st.voiceReady ? "no voice" : (st.muted ? "muted" : "voice on"))
    + " · " + st.provider

  function change(key, value) {
    Quickshell.execDetached(["python3", root.pluginDir + "/daemon/settings.py", "set", key, String(value)])
    refreshTimer.restart()           // the checklist depends on the agent, so look again once the file is written
  }
  function refreshChecks() { if (!doctor.running) doctor.running = true }
  onOpenedChanged: if (opened) refreshChecks()
  Timer { id: refreshTimer; interval: 500; onTriggered: root.refreshChecks() }

  Process {
    id: doctor
    command: ["python3", root.pluginDir + "/daemon/doctor.py"]
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var d = JSON.parse(text)
          root.checks = d.checks
          root.providers = d.providers
        } catch (e) {}
      }
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰊠"
    slotSize: Style.bar.iconSlot
    tooltipText: ""
    onPressed: function(b) { root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(14)

        // ---------- hero ----------
        Row {
          spacing: Style.space(12)
          Text {
            text: "󰊠"
            font.family: root.fontFamily
            font.pixelSize: Style.font.display
            color: root.fg
            anchors.verticalCenter: parent.verticalCenter
          }
          Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "Goop"; color: root.fg; font.family: root.fontFamily; font.pixelSize: Style.font.title; font.bold: true }
            Text { text: root.summary; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall }
          }
        }

        // ---------- animations ----------
        PanelSeparator { foreground: root.fg }
        Column {
          width: parent.width
          spacing: Style.space(10)
          PanelSectionHeader { text: "ANIMATIONS"; foreground: root.fg; fontFamily: root.fontFamily }
          Row {
            id: animRow
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: [{ k: "full", t: "Full" }, { k: "reduced", t: "Reduced" }, { k: "off", t: "Off" }]
              Button {
                required property var modelData
                width: (animRow.width - animRow.spacing * 2) / 3
                text: modelData.t
                fontSize: Style.font.bodySmall
                foreground: root.fg
                fontFamily: root.fontFamily
                horizontalPadding: Style.spacing.controlPaddingX
                verticalPadding: Style.spacing.controlPaddingY + Style.space(2)
                bordered: true
                active: root.st.animations === modelData.k
                onClicked: root.change("animations", modelData.k)
              }
            }
          }
          Text {
            width: parent.width
            wrapMode: Text.Wrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            text: root.st.animations === "full" ? "Liquid wobble, jelly breathing and drips. Uses the most CPU."
                : root.st.animations === "reduced" ? "Plain round goops that still blink and look at the cursor."
                : "Static goops. The lightest setting for older machines."
          }
        }

        // ---------- voice ----------
        PanelSeparator { foreground: root.fg }
        Column {
          width: parent.width
          spacing: Style.space(10)
          PanelSectionHeader { text: "VOICE"; foreground: root.fg; fontFamily: root.fontFamily }
          Toggle {
            width: parent.width
            label: "Speak replies"
            description: root.st.voiceReady ? "On-device, nothing leaves your machine" : "Voice is not installed yet (see Setup below)"
            checked: !root.st.muted
            foreground: root.fg
            fontFamily: root.fontFamily
            onClicked: root.change("tts.muted", root.st.muted ? "false" : "true")
          }
        }

        // ---------- agent ----------
        PanelSeparator { foreground: root.fg }
        Column {
          width: parent.width
          spacing: Style.space(10)
          PanelSectionHeader { text: "AGENT"; foreground: root.fg; fontFamily: root.fontFamily }
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: root.providers
              Button {
                required property var modelData
                text: modelData.name + (modelData.ready ? "" : "  ✗")
                fontSize: Style.font.bodySmall
                foreground: root.fg
                fontFamily: root.fontFamily
                horizontalPadding: Style.spacing.controlPaddingX
                verticalPadding: Style.spacing.controlPaddingY + Style.space(2)
                bordered: true
                active: modelData.active
                onClicked: root.change("provider", modelData.name)
              }
            }
          }
          Text {
            visible: !!root.activeProvider && !root.activeProvider.ready
            width: parent.width
            wrapMode: Text.Wrap
            color: root.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            text: root.activeProvider ? root.activeProvider.problem : ""
          }
          Text {
            visible: root.providers.length <= 1
            width: parent.width
            wrapMode: Text.Wrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            text: "More agents (OpenAI, Grok, Gemini, Ollama...) are added in the config file; see the docs."
          }
        }

        // ---------- setup checklist ----------
        PanelSeparator { foreground: root.fg }
        Column {
          width: parent.width
          spacing: Style.space(8)
          PanelSectionHeader { text: "SETUP"; foreground: root.fg; fontFamily: root.fontFamily }
          Text {   // healthy: one line. Otherwise: only what needs attention is listed below.
            visible: root.checks.length > 0
            width: parent.width
            wrapMode: Text.Wrap
            color: root.problems.length === 0 ? root.fg : root.dim
            opacity: root.problems.length === 0 ? 0.75 : 1
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            text: root.problems.length === 0 ? "✓ Everything is set up"
                : (root.checks.length - root.problems.length) + " of " + root.checks.length + " checks passed"
          }
          Repeater {
            model: root.problems
            Row {
              required property var modelData
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: modelData.ok ? "✓" : (modelData.required ? "✗" : "○")
                color: modelData.ok ? root.fg : root.urgent
                opacity: modelData.ok ? 0.6 : 1
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Column {
                width: parent.width - Style.space(24)
                Text { text: modelData.label; color: root.fg; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall }
                Text {
                  visible: !modelData.ok
                  width: parent.width
                  wrapMode: Text.Wrap
                  text: modelData.hint
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }
          }
          Button {
            visible: root.voiceMissing
            text: "Set up voice"
            fontSize: Style.font.bodySmall
            foreground: root.fg
            fontFamily: root.fontFamily
            bordered: true
            horizontalPadding: Style.spacing.controlPaddingX
            verticalPadding: Style.spacing.controlPaddingY + Style.space(2)
            onClicked: { Quickshell.execDetached(["xdg-terminal-exec", root.pluginDir + "/setup.sh"]); root.close() }
          }
        }

        // ---------- footer ----------
        Row {
          width: parent.width
          spacing: Style.space(6)
          Button {
            text: "Open config"
            fontSize: Style.font.bodySmall
            foreground: root.fg
            fontFamily: root.fontFamily
            horizontalPadding: Style.spacing.controlPaddingX
            verticalPadding: Style.spacing.controlPaddingY
            onClicked: {
              Quickshell.execDetached(["bash", "-c", "mkdir -p ~/.config/goop && [ -f ~/.config/goop/config.json ] || echo '{}' > ~/.config/goop/config.json; xdg-open ~/.config/goop/config.json"])
              root.close()
            }
          }
          Button {
            text: "Docs"
            fontSize: Style.font.bodySmall
            foreground: root.fg
            fontFamily: root.fontFamily
            horizontalPadding: Style.spacing.controlPaddingX
            verticalPadding: Style.spacing.controlPaddingY
            onClicked: { Quickshell.execDetached(["xdg-open", root.pluginDir + "/README.md"]); root.close() }
          }
        }
      }
    }
  }
}
