// Brand mark component. Inline SVG of an isometric block with the
// letter B on the front face, in the visual language of a modern
// knowledge tool: thick black outline, restrained perspective,
// serif letterform. Sized via the size prop in pixels.
//
// This is intentionally an inline SVG rather than an imported asset
// file so the brand mark lives entirely in code. To swap in a real
// asset, drop a file at src/assets/logo.svg and replace this
// component's body with a single <img> tag pointing at the import.

interface Props {
  size?: number;
  className?: string;
}

export default function Logo({ size = 40, className = "" }: Props) {
  // viewBox dimensions chosen so the cube fills most of the box with
  // a small margin for the outline stroke. The shape is composed of
  // three polygons (top, side, front) layered back-to-front so the
  // outlines compose into a single cube outline.
  return (
    <svg
      viewBox="0 0 100 110"
      width={size}
      height={size * (110 / 100)}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Compliance Troubleshooter"
    >
      {/* Side face (drawn first so the front face overlaps it cleanly) */}
      <polygon
        points="80,28 92,16 92,88 80,100"
        fill="#FFFFFF"
        stroke="#1F1E1B"
        strokeWidth="4"
        strokeLinejoin="round"
      />
      {/* Top face */}
      <polygon
        points="20,28 80,28 92,16 32,16"
        fill="#FFFFFF"
        stroke="#1F1E1B"
        strokeWidth="4"
        strokeLinejoin="round"
      />
      {/* Front face */}
      <rect
        x="20"
        y="28"
        width="60"
        height="72"
        fill="#FFFFFF"
        stroke="#1F1E1B"
        strokeWidth="4"
        strokeLinejoin="round"
      />
      {/* The B. Serif slab matching the asset pack feel. */}
      <text
        x="50"
        y="84"
        textAnchor="middle"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="56"
        fontWeight="700"
        fill="#1F1E1B"
      >
        B
      </text>
    </svg>
  );
}
