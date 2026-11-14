import { QUANTITIES, type Quantity, type SessionData } from "@/session/store";

/** The measured T range of one file, in K as the server read it. */
export interface TemperatureRange {
  min_temperature_k: number;
  max_temperature_k: number;
}

/**
 * Two files whose T ranges suggest that one is in another unit: `shifted` by about 273.15 K at
 * both ends, as °C read as K gives, or `apart`, with no T in common.
 */
export interface RangeMismatch {
  kind: "shifted" | "apart";
  first: Quantity;
  second: Quantity;
}

const CELSIUS_OFFSET_K = 273.15;
/**
 * How far from 273.15 K both ends may be and still count as shifted. Files of one sample are often
 * measured between the same set points, so both ends move by the offset. A tenth of it leaves room
 * for set points a few kelvin apart, and keeps a range that only starts 273 K higher out.
 */
const SHIFT_TOLERANCE_K = 0.1 * CELSIUS_OFFSET_K;

function isOffset(difference: number): boolean {
  return Math.abs(Math.abs(difference) - CELSIUS_OFFSET_K) <= SHIFT_TOLERANCE_K;
}

function mismatchOf(
  a: TemperatureRange,
  b: TemperatureRange,
): RangeMismatch["kind"] | null {
  const low = a.min_temperature_k - b.min_temperature_k;
  const high = a.max_temperature_k - b.max_temperature_k;
  if (Math.sign(low) === Math.sign(high) && isOffset(low) && isOffset(high)) {
    return "shifted";
  }
  if (
    a.max_temperature_k < b.min_temperature_k ||
    b.max_temperature_k < a.min_temperature_k
  ) {
    return "apart";
  }
  return null;
}

/**
 * Pairs of separate files whose T ranges look like different units of T. Nothing is changed: T is
 * read as each file says, and only a user knows which is right. A hint, not a check, as files can
 * cover different ranges on purpose.
 */
export function temperatureMismatches(
  ranges: Partial<Record<Quantity, TemperatureRange>>,
): RangeMismatch[] {
  const loaded = QUANTITIES.filter(
    (quantity) => ranges[quantity] !== undefined,
  );
  return loaded.flatMap((first, index) =>
    loaded.slice(index + 1).flatMap((second) => {
      const a = ranges[first];
      const b = ranges[second];
      const kind = a && b ? mismatchOf(a, b) : null;
      return kind === null ? [] : [{ kind, first, second }];
    }),
  );
}

/** The mismatches between the files of a session, by their measured ranges. */
export function sessionMismatches(
  data: Partial<Record<Quantity, Pick<SessionData, "measurement">>>,
): RangeMismatch[] {
  return temperatureMismatches(
    Object.fromEntries(
      QUANTITIES.flatMap((quantity) => {
        const measurement = data[quantity]?.measurement;
        return measurement === undefined ? [] : [[quantity, measurement]];
      }),
    ),
  );
}
