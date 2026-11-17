/** ETB helpers. Every amount is an integer number of santim. */
export const SANTIM_PER_BIRR = 100;
export const CURRENCY = "ETB";

export class MoneyError extends Error {}

export function parseMoney(value: string | number): number {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new MoneyError("Money must be finite");
    return Math.round(value * SANTIM_PER_BIRR);
  }
  let text = value.trim().replace(/[,_\s]/g, "");
  for (const prefix of ["ETB", "ብር", "Br"]) {
    if (text.toUpperCase().startsWith(prefix.toUpperCase())) {
      text = text.slice(prefix.length);
      break;
    }
  }
  if (!/^-?\d+(\.\d+)?$/.test(text)) throw new MoneyError(`Cannot parse money value ${value}`);
  return Math.round(Number(text) * SANTIM_PER_BIRR);
}

export function formatSantim(amount: number, options: { locale?: string; withCurrency?: boolean } = {}): string {
  if (!Number.isInteger(amount)) throw new MoneyError("Amount must be integer santim");
  const { locale = "en", withCurrency = true } = options;
  const sign = amount < 0 ? "-" : "";
  const absolute = Math.abs(amount);
  const whole = Math.floor(absolute / SANTIM_PER_BIRR);
  const part = absolute % SANTIM_PER_BIRR;
  const body = `${sign}${whole.toLocaleString("en-US")}.${String(part).padStart(2, "0")}`;
  if (!withCurrency) return body;
  return locale === "am" ? `ብር ${body}` : `ETB ${body}`;
}

export function allocate(amount: number, weights: number[]): number[] {
  if (weights.length === 0) throw new MoneyError("At least one weight is required");
  if (weights.some((w) => w < 0)) throw new MoneyError("Weights cannot be negative");
  const total = weights.reduce((sum, w) => sum + w, 0);
  if (total === 0) throw new MoneyError("Weights cannot all be zero");
  const sign = amount < 0 ? -1 : 1;
  const absolute = Math.abs(amount);
  const shares = weights.map((w) => Math.floor((absolute * w) / total));
  let remainder = absolute - shares.reduce((sum, s) => sum + s, 0);
  const order = weights.map((_, i) => i).sort((a, b) => weights[b] - weights[a] || a - b);
  for (let i = 0; remainder > 0; i += 1, remainder -= 1) {
    shares[order[i % order.length]] += 1;
  }
  return shares.map((s) => sign * s);
}
