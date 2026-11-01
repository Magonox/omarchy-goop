import QtQuick

// A small microphone drawn from rectangles (no icon font needed): a capsule in a cradle on a stem. 24 x 24.
Item {
    property color fg: "white"
    width: 24; height: 24
    Rectangle { x: 9; y: 5; width: 6; height: 10; radius: 3; color: parent.fg }                                              // the capsule
    Rectangle { x: 7; y: 11; width: 10; height: 6; radius: 3; color: "transparent"; border.width: 1.5; border.color: parent.fg }  // the cradle
    Rectangle { x: 11.25; y: 17; width: 1.5; height: 3; color: parent.fg }                                                   // the stem
}
