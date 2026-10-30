"""The visual vocabulary: everything a storyboard may ask for. The model names parts by kind, material and relation; the layout code decides
where they go. Dimensions are in metres-ish scene units. `axial` kinds are built standing on the y axis and laid on their side by the axis
template; `spanning` kinds (casing, shaft) are stretched over a run of other parts."""

SIZES = {"small": 0.65, "medium": 1.0, "large": 1.4, "huge": 1.9}

MATERIALS = {   # name -> color, metalness, roughness, emissive strength
    "steel": {"color": [168, 178, 194], "metal": 0.3, "rough": 0.4, "emissive": 0},
    "dark_steel": {"color": [96, 106, 124], "metal": 0.25, "rough": 0.45, "emissive": 0},
    "copper": {"color": [214, 124, 70], "metal": 0.35, "rough": 0.35, "emissive": 0},
    "gold": {"color": [226, 184, 80], "metal": 0.35, "rough": 0.35, "emissive": 0},
    "white": {"color": [236, 238, 244], "metal": 0.1, "rough": 0.5, "emissive": 0},
    "red": {"color": [210, 66, 70], "metal": 0.3, "rough": 0.45, "emissive": 0},
    "orange": {"color": [232, 132, 60], "metal": 0.3, "rough": 0.45, "emissive": 0},
    "blue": {"color": [70, 130, 220], "metal": 0.3, "rough": 0.4, "emissive": 0},
    "green": {"color": [86, 170, 110], "metal": 0.2, "rough": 0.6, "emissive": 0},
    "solar": {"color": [44, 80, 168], "metal": 0.3, "rough": 0.25, "emissive": 0},
    "concrete": {"color": [186, 186, 192], "metal": 0.0, "rough": 0.9, "emissive": 0},
    "glass": {"color": [170, 210, 255], "metal": 0.0, "rough": 0.08, "emissive": 0, "alpha": 0.2},
    "flame": {"color": [255, 150, 60], "metal": 0.0, "rough": 0.5, "emissive": 1.0},
}

KINDS = {
    # a jet engine and other things in a row
    "fan": {"type": "fan", "r": 1.35, "h": 0.5, "blades": 12, "axial": True, "material": "steel"},
    "compressor": {"type": "stages", "r0": 1.2, "r1": 0.8, "h": 1.7, "n": 3, "blades": 10, "axial": True, "material": "steel"},
    "chamber": {"type": "chamber", "r": 0.95, "h": 1.5, "axial": True, "material": "copper"},
    "turbine": {"type": "stages", "r0": 0.85, "r1": 0.85, "h": 1.0, "n": 2, "blades": 10, "axial": True, "material": "gold"},
    "nozzle": {"type": "nozzle", "r0": 0.9, "r1": 0.55, "h": 1.1, "axial": True, "material": "steel"},
    "casing": {"type": "casing", "r": 1.5, "axial": True, "spanning": True, "material": "glass"},
    "shaft": {"type": "shaft", "r": 0.12, "axial": True, "spanning": True, "material": "white"},
    # signals in a room
    "router": {"type": "router", "r": 0.5, "h": 0.5, "material": "white"},
    "tower": {"type": "tower", "r": 0.5, "h": 2.4, "material": "steel"},      # a transmitter: radio or TV mast
    "device": {"type": "device", "variant": "laptop", "r": 0.6, "h": 0.6, "material": "dark_steel"},
    "wall": {"type": "wall", "w": 3.6, "h": 2.4, "t": 0.25, "r": 1.8, "material": "concrete"},
    # a vehicle made of parts
    "capsule": {"type": "capsule", "r": 1.05, "h": 1.7, "material": "white"},
    "module": {"type": "module", "r": 1.05, "h": 1.8, "material": "steel"},
    "tank": {"type": "tank", "r": 0.7, "h": 1.2, "material": "orange"},
    "engine": {"type": "engine", "r": 0.95, "h": 1.3, "material": "steel"},
    "panel": {"type": "panel", "w": 3.4, "d": 1.3, "r": 1.7, "h": 0.1, "material": "solar"},
    "dish": {"type": "dish", "r": 0.7, "h": 0.6, "material": "white"},
    "thruster": {"type": "thruster", "r": 0.18, "h": 0.35, "material": "dark_steel"},
    # anything else: the model describes the part as a recipe of basic pieces (see custom.py)
    "custom": {"type": "custom", "r": 1.0, "h": 1.0, "material": "steel"},
    # plain shapes for anything else
    "box": {"type": "box", "w": 1.2, "h": 1.0, "d": 1.2, "r": 0.9, "material": "steel"},
    "cylinder": {"type": "cylinder", "r": 0.6, "h": 1.2, "material": "steel"},
    "sphere": {"type": "sphere", "r": 0.7, "h": 1.4, "material": "blue"},
    "cone": {"type": "cone", "r": 0.7, "h": 1.2, "material": "red"},
}

TEMPLATES = ("axis", "network", "assembly")
VERBS = ("reveal", "label", "highlight", "flow", "spin", "explode", "pulse", "zoom", "cutaway")
MEDIA = {"air": [200, 230, 255], "fuel": [255, 190, 90], "exhaust": [255, 140, 60], "water": [120, 190, 255], "power": [255, 236, 130], "signal": [150, 220, 255]}
ATTACH_AT = ("top", "bottom", "left", "right", "sides", "front", "back", "ring")
RESERVED_IDS = ("floor",)
DISTANCES = {"near": 3.4, "medium": 6.2, "far": 9.0}
LIMITS = {"parts": (2, 14), "steps": (2, 12), "say": (10, 420), "label": 24, "title": 80, "analogy": 220, "duration": 170}
