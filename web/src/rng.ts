// Seedable RNG. We do not clone CPython's Mersenne stream; determinism comes
// from seeds and explicit mine layouts (see the plan). `mulberry32` is a small,
// fast, well-distributed 32-bit generator.

export type Rng = () => number; // returns a float in [0, 1)

export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Sample `k` distinct items from `items` using `rng` (partial Fisher–Yates). */
export function sample<T>(items: readonly T[], k: number, rng: Rng): T[] {
  const pool = items.slice();
  const n = pool.length;
  const out: T[] = [];
  for (let i = 0; i < k; i++) {
    const j = i + Math.floor(rng() * (n - i));
    const tmp = pool[i]!;
    pool[i] = pool[j]!;
    pool[j] = tmp;
    out.push(pool[i]!);
  }
  return out;
}
