import { QUANTITIES, type Quantity, type SessionData } from "@/session/store";

/** The measured T range of one file, in K as the server read it. */
export interface TemperatureRange {
  min_temperature_k: number;
  max_temperature_k: number;
}

/**
 * Two files whose T ranges are about 273.15 K apart at both ends, as °C read as K gives: T of
 * `lower` sits below T of `higher` by the offset.
 */
export interface RangeMismatch {
  lower: Quantity;
  higher: Quantity;
}

const CELSIUS_OFFSET_K = 273.15;
/**
 * How far from 273.15 K each end may be. Files of one sample measured between the same set points
 * move by the offset at both ends, give or take rounding of the set points. Ranges that only meet,
 * such as a Hall run to 300 K beside an S run from 300 K, differ by more at one end, and do not
 * count: 2–300 K beside 300–573 K are 298 K and 273 K apart.
 */
const SHIFT_TOLERANCE_K = 10;

function isOffset(difference: number): boolean {
  return Math.abs(difference - CELSIUS_OFFSET_K) <= SHIFT_TOLERANCE_K;
}

/** Which of two ranges sits about 273 K below the other at both ends, if either. */
function lowerOf(a: TemperatureRange, b: TemperatureRange): "a" | "b" | null {
  const shiftedBy = (low: TemperatureRange, high: TemperatureRange) =>
    isOffset(high.min_temperature_k - low.min_temperature_k) &&
    isOffset(high.max_temperature_k - low.max_temperature_k);
  if (shiftedBy(a, b)) {
    return "a";
  }
  return shiftedBy(b, a) ? "b" : null;
}

/**
 * Pairs of separate files whose T ranges look like K beside °C read as K. Nothing is changed: T is
 * read as each file says, and only a user knows which is right. A hint, not a check, as two runs
 * can also cover such ranges on purpose.
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
      const lower = a && b ? lowerOf(a, b) : null;
      if (lower === null) {
        return [];
      }
      return [
        lower === "a"
          ? { lower: first, higher: second }
          : { lower: second, higher: first },
      ];
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
