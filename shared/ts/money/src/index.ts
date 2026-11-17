/**
 * ETB helpers. Amounts are integer santim everywhere (ARCH §5.9).
 *
 * Parsing deliberately works on the decimal text rather than multiplying a
 * float by 100: `1.005 * 100` is `100.49999999999999` in IEEE-754, which would
 * silently round a half-santim the wrong way. Santim values must stay inside
 * Number.MAX_SAFE_INTEGER, so amounts above ~90 trillion birr are rejected
 * instead of losing precision.
 */
export const SANTIM_PER_BIRR = 100;
export const CURRENCY = "ETB";
export const MAX_SANTIM = Number.MAX_SAFE_INTEGER;

export class MoneyError extends Error {}

const CURRENCY_PREFIXES = ["ETB", "ብር", "Br"];
const PLAIN_DECIMAL = /^([+-]?)(\d+)(?:\.(\d+))?$/;

function toSantim(text: string): number {
  const match = PLAIN_DECIMAL.exec(text);
  if (!match) throw new MoneyError(`Cannot parse money value ${text}`);
  const [, sign, wholeDigits, fraction = ""] = match;
  const whole = Number(wholeDigits);
  if (!Number.isSafeInteger(whole * SANTIM_PER_BIRR)) {
    throw new MoneyError("Money amount is too large");
  }
  let santim = whole * SANTIM_PER_BIRR;
  santim += Number((fraction + "00").slice(0, 2));
  const rest = (fraction + "00").slice(2);
  // Round half up on the third decimal digit; amounts are never truncated.
  if (rest !== "" && Number(rest[0]) >= 5) santim += 1;
  if (!Number.isSafeInteger(santim)) throw new MoneyError("Money amount is too large");
  return sign === "-" ? -santim : santim;
}

export function parseMoney(value: string | number): number {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new MoneyError("Money must be finite");
    const text = String(value);
    if (!PLAIN_DECIMAL.test(text)) {
      throw new MoneyError(`Cannot parse money value ${value}`);
    }
    return toSantim(text);
  }
  let text = String(value).trim().replace(/[,_\s]/g, "");
  for (const prefix of CURRENCY_PREFIXES) {
    if (text.toUpperCase().startsWith(prefix.toUpperCase())) {
      text = text.slice(prefix.length);
      break;
    }
  }
  return toSantim(text);
}

export function formatSantim(
  amount: number,
  options: { locale?: string; withCurrency?: boolean } = {},
): string {
  if (!Number.isSafeInteger(amount)) {
    throw new MoneyError("Amount must be an integer number of santim");
  }
  const { locale = "en", withCurrency = true } = options;
  const sign = amount < 0 ? "-" : "";
  const absolute = Math.abs(amount);
  const whole = Math.floor(absolute / SANTIM_PER_BIRR);
  const part = absolute % SANTIM_PER_BIRR;
  const body = `${sign}${whole.toLocaleString("en-US")}.${String(part).padStart(2, "0")}`;
  if (!withCurrency) return body;
  return locale === "am" ? `ብር ${body}` : `ETB ${body}`;
}

export function add(...amounts: number[]): number {
  let total = 0;
  for (const amount of amounts) {
    if (!Number.isSafeInteger(amount)) {
      throw new MoneyError("Amount must be an integer number of santim");
    }
    total += amount;
    if (!Number.isSafeInteger(total)) throw new MoneyError("Money amount is too large");
  }
  return total;
}

export function subtract(left: number, right: number): number {
  return add(left, -right);
}

/**
 * Split `amount` across `weights` without losing or inventing a santim.
 * Leftover santim go to the largest weights first, ties by original order,
 * so the same inputs always produce the same shares. Negative amounts split
 * symmetrically (the sign is applied after allocating the absolute value).
 */
export function allocate(amount: number, weights: number[]): number[] {
  if (!Number.isSafeInteger(amount)) {
    throw new MoneyError("Amount must be an integer number of santim");
  }
  if (weights.length === 0) throw new MoneyError("At least one weight is required");
  if (weights.some((weight) => weight < 0)) {
    throw new MoneyError("Weights cannot be negative");
  }
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  if (total === 0) throw new MoneyError("Weights cannot all be zero");
  if (!Number.isFinite(total)) throw new MoneyError("Weights are too large");

  const sign = amount < 0 ? -1 : 1;
  const absolute = Math.abs(amount);
  const shares = weights.map((weight) => Math.floor((absolute * weight) / total));
  let remainder = absolute - shares.reduce((sum, share) => sum + share, 0);
  const order = weights
    .map((_, index) => index)
    .sort((left, right) => weights[right] - weights[left] || left - right);
  for (let index = 0; remainder > 0; index += 1, remainder -= 1) {
    shares[order[index % order.length]] += 1;
  }
  return shares.map((share) => sign * share);
}
