import { fontSize, spacing, touchTarget } from "@erp/tokens";

/**
 * Native layout tokens (ARCH §11.5). Colours and radii come from the school
 * theme at runtime; spacing, type and touch sizes are the shared fixed scales,
 * so a community theme can never break a layout.
 */
export const space = spacing;

export const text = fontSize;

export const weight = {
  regular: "400" as const,
  medium: "500" as const,
  semibold: "600" as const,
};

/** iOS asks for 44 pt, Android for 48 dp. One target satisfies both. */
export const touch = touchTarget.android;

export const radius = {
  sm: 8,
  md: 10,
  lg: 14,
  pill: 999,
} as const;

export const font = {
  /** The Ethiopic face is bundled; it also carries a usable Latin subset. */
  family: "NotoSansEthiopic",
} as const;
