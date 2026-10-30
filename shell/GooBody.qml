import QtQuick
import QtQuick.Shapes
import "goo.js" as Goo

// A goop's body: a liquid blob (see goo.js). `t` is the shared clock in seconds; `energy` makes it wobble livelier.
Item {
    id: body
    property color color: "#e5484d"
    property real r: 13
    property int seed: 0
    property real squish: 0
    property real energy: 0
    property real t: 0
    width: r * 2
    height: r * 2

    Shape {
        width: body.width
        height: body.height
        preferredRendererType: Shape.CurveRenderer     // smooth anti-aliased edges without multisampling
        ShapePath {
            fillColor: body.color
            strokeWidth: -1
            PathSvg { path: Goo.svg(Goo.points(body.r, body.r, body.r, body.t, body.seed, body.squish, body.energy)) }
        }
    }
}
