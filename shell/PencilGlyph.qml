import QtQuick

// A small pencil drawn from rectangles, for "type it". 24 x 24.
Item {
    property color fg: "white"
    width: 24; height: 24
    Item {
        anchors.centerIn: parent
        width: 20; height: 20
        rotation: 45
        Rectangle { x: 7.5; y: 1; width: 5; height: 12; radius: 1; color: parent.parent.fg }     // the body
        Rectangle { x: 7.5; y: 13; width: 5; height: 4; color: "#f0c987" }                       // the wood
        Rectangle { x: 9; y: 17; width: 2; height: 2.5; color: "#55555d" }                       // the lead
    }
}
