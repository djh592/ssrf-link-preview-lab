// The two scenes contain the same Compose topology at different aspect ratios.
export const SCENES = {
  wide: {
    width: 1120,
    height: 530,
    testbed: { x: 204, y: 160, width: 712, height: 355, labelX: 220 },
    previewContainer: { x: 487, y: 252, width: 211, height: 180, labelX: 500 },
    devices: {
      browser: { x: 77, y: 90, hit: [-5, -5, 92, 100, 0, 70] },
      preview: { x: 510, y: 292, hit: [-5, -5, 82, 150, 0, 96] },
      dns: { x: 616, y: 278, hit: [-5, -5, 66, 110, 0, 65] },
      "external-page": { x: 300, y: 305, labelAbove: true, hit: [-5, -40, 82, 140, 35, 94] },
      "internal-report": { x: 748, y: 305, labelAbove: true, hit: [-5, -40, 82, 140, 35, 94] },
      "public-web": { x: 967, y: 89, labelAbove: true, hit: [-5, -14, 100, 85, 9, 70] },
    },
    networks: [
      { id: "public", label: "public_egress", x1: 540, x2: 865, y: 218, ports: [546, 865], labelY: 205 },
      { id: "external", label: "external_zone", x1: 286, x2: 550, y: 465, ports: [336, 495] },
      { id: "internal", label: "internal_zone", x1: 570, x2: 834, y: 465, ports: [597, 784] },
    ],
    routes: {
      browser: [[159, 124], [182, 124], [182, 238], [476, 238], [476, 314], [510, 314]],
      "external-page": [[510, 352], [495, 352], [495, 465], [336, 465], [336, 393]],
      "internal-report": [[582, 352], [597, 352], [597, 465], [784, 465], [784, 393]],
      "public-web": [[546, 292], [546, 218], [865, 218], [865, 183], [1011, 183], [1011, 149]],
      dns: [[582, 316], [603, 316], [603, 308], [616, 308]],
    },
    stops: {
      "external-page": [504, 352],
      "internal-report": [588, 352],
      "public-web": [546, 285],
      default: [546, 330],
    },
  },
  narrow: {
    width: 360,
    height: 700,
    testbed: { x: 15, y: 183, width: 330, height: 502, labelX: 128 },
    previewContainer: { x: 113, y: 266, width: 190, height: 180, labelX: 188 },
    devices: {
      browser: { x: 25, y: 51, hit: [-5, -5, 92, 100, 0, 70] },
      preview: { x: 136, y: 308, hit: [-5, -5, 82, 150, 0, 96] },
      dns: { x: 237, y: 292, hit: [-5, -5, 66, 110, 0, 65] },
      "external-page": { x: 54, y: 515, hit: [-5, -5, 82, 145, 0, 94] },
      "internal-report": { x: 234, y: 515, hit: [-5, -5, 82, 145, 0, 94] },
      "public-web": { x: 247, y: 52, labelAbove: true, hit: [-5, -14, 100, 85, 9, 70] },
    },
    networks: [
      { id: "public", label: "public_egress", x1: 160, x2: 270, y: 248, ports: [172, 270], labelX: 194, labelY: 238 },
      { id: "external", label: "external_zone", x1: 38, x2: 154, y: 468, ports: [90, 128] },
      { id: "internal", label: "internal_zone", x1: 206, x2: 322, y: 468, ports: [216, 270] },
    ],
    routes: {
      browser: [[107, 85], [122, 85], [122, 330], [136, 330]],
      "external-page": [[136, 370], [128, 370], [128, 468], [90, 468], [90, 515]],
      "internal-report": [[208, 370], [216, 370], [216, 468], [270, 468], [270, 515]],
      "public-web": [[172, 308], [172, 248], [270, 248], [270, 149], [291, 149], [291, 112]],
      dns: [[208, 332], [224, 332], [224, 322], [237, 322]],
    },
    stops: {
      "external-page": [130, 370],
      "internal-report": [214, 370],
      "public-web": [172, 301],
      default: [172, 346],
    },
  },
};
