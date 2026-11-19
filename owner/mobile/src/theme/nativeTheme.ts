import { DEFAULT_THEME, toReactNativeTheme, type ThemeDefinition, type TokenSet } from "@erp/tokens";

import type { ThemeMode } from "./useSchoolTheme";

interface Oklch {
  lightness: number;
  chroma: number;
  hue: number;
  alpha: number;
}

const OKLCH_PATTERN =
  /^oklch\(\s*([0-9.]+%?)\s+([0-9.]+%?)\s+([0-9.]+)(?:deg)?\s*(?:\/\s*([0-9.]+%?))?\s*\)$/i;

function parseComponent(value: string | undefined, scale: number, percentScale: number): number {
  if (value === undefined) return 0;
  if (value.endsWith("%")) return (Number.parseFloat(value) / 100) * percentScale;
  return Number.parseFloat(value) * scale;
}

function parseOklch(value: string): Oklch | null {
  const match = OKLCH_PATTERN.exec(value.trim());
  if (!match) return null;
  const lightness = match[1]!.endsWith("%")
    ? Number.parseFloat(match[1]!) / 100
    : Number.parseFloat(match[1]!);
  const chroma = match[2]!.endsWith("%")
    ? (Number.parseFloat(match[2]!) / 100) * 0.4
    : Number.parseFloat(match[2]!);
  const hue = Number.parseFloat(match[3]!);
  const alpha = match[4] === undefined ? 1 : parseComponent(match[4], 1, 1);
  if (![lightness, chroma, hue, alpha].every(Number.isFinite)) return null;
  return { lightness, chroma, hue, alpha };
}

function linearToSrgb(channel: number): number {
  const clamped = Math.min(1, Math.max(0, channel));
  return clamped <= 0.0031308 ? 12.92 * clamped : 1.055 * clamped ** (1 / 2.4) - 0.055;
}

function toHexByte(value: number): string {
  return Math.round(Math.min(1, Math.max(0, value)) * 255)
    .toString(16)
    .padStart(2, "0");
}

export function oklchToRgb(value: string): string | null {
  const colour = parseOklch(value);
  if (!colour) return null;
  const radians = (colour.hue * Math.PI) / 180;
  const a = colour.chroma * Math.cos(radians);
  const b = colour.chroma * Math.sin(radians);
  const lPrime = colour.lightness + 0.3963377774 * a + 0.2158037573 * b;
  const mPrime = colour.lightness - 0.1055613458 * a - 0.0638541728 * b;
  const sPrime = colour.lightness - 0.0894841775 * a - 1.291485548 * b;
  const l = lPrime ** 3;
  const m = mPrime ** 3;
  const s = sPrime ** 3;
  const red = linearToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const green = linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const blue = linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);
  if (colour.alpha >= 0.999) {
    return `#${toHexByte(red)}${toHexByte(green)}${toHexByte(blue)}`;
  }
  const alpha = Math.round(Math.min(1, Math.max(0, colour.alpha)) * 1000) / 1000;
  return `rgba(${Math.round(red * 255)}, ${Math.round(green * 255)}, ${Math.round(blue * 255)}, ${alpha})`;
}

/** Converts CSS colour tokens to values React Native can parse. */
export function nativeTokenSet(tokens: TokenSet): TokenSet {
  const converted: TokenSet = { ...tokens };
  for (const [key, value] of Object.entries(tokens)) {
    if (typeof value !== "string") continue;
    const colour = oklchToRgb(value);
    if (colour) converted[key] = colour;
  }
  return converted;
}

export function nativeThemeFrom(theme: ThemeDefinition, mode: ThemeMode) {
  const tokens = theme.tokens[mode] ?? DEFAULT_THEME.tokens[mode];
  return toReactNativeTheme(nativeTokenSet(tokens));
}

export function defaultNativeTheme(mode: ThemeMode) {
  return nativeThemeFrom(DEFAULT_THEME, mode);
}
