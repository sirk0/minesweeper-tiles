// Tactile feedback for game events. Two moments buzz: placing a flag (a light
// tick) and losing (a stronger pattern). The mechanism is chosen at call time
// by feature detection, because the platforms disagree on what's available:
//
//   - Android/Chrome (and anything else with the Vibration API): navigator
//     .vibrate takes a pattern, so we get real, distinct feedback per event.
//   - iOS Safari — including a standalone/home-screen PWA — does NOT implement
//     navigator.vibrate at all (it's undefined). The only web haptic that
//     reaches iOS 17.4+ is the "switch" trick: toggling a hidden
//     <input type="checkbox" switch> plays a light system tick. It's one fixed
//     intensity, so "lose" just repeats it to feel stronger.
//   - Desktop and headless test browsers: navigator.vibrate is typically a
//     no-op function, so they take the first branch and do nothing visible —
//     harmless, and it keeps the test seam (window.__ms) side-effect-free.
//
// All global access is guarded so importing this module under the node unit
// test environment (no window/navigator/document) is safe, and the hidden
// switch element is created lazily on first use rather than at import time.
//
// This is the single seam for haptics: if the app is later packaged natively
// (e.g. a Capacitor WKWebView with @capacitor/haptics, or Core Haptics), swap
// the implementation here and the call sites in session.ts stay unchanged.

export type HapticKind = "flag" | "lose";

// Vibration patterns (ms). A single short pulse for a flag; a heavier
// buzz-buzz-BUZZ for a loss.
const PATTERNS: Record<HapticKind, number | number[]> = {
  flag: 15,
  lose: [40, 30, 40, 30, 80],
};

function canVibrate(): boolean {
  return (
    typeof navigator !== "undefined" && typeof navigator.vibrate === "function"
  );
}

let iosSwitch: HTMLLabelElement | null = null;

// Lazily build the hidden <label><input type="checkbox" switch></label>. iOS
// plays a haptic tick when a switch-styled checkbox is toggled by a click, so
// clicking the label is how we ask for feedback on iOS.
function iosSwitchElement(): HTMLLabelElement | null {
  if (typeof document === "undefined") return null;
  if (iosSwitch) return iosSwitch;
  const label = document.createElement("label");
  label.setAttribute("aria-hidden", "true");
  Object.assign(label.style, {
    position: "absolute",
    width: "1px",
    height: "1px",
    overflow: "hidden",
    opacity: "0",
    pointerEvents: "none",
  });
  const input = document.createElement("input");
  input.type = "checkbox";
  input.setAttribute("switch", ""); // Safari-only switch appearance -> haptic
  label.appendChild(input);
  document.body.appendChild(label);
  iosSwitch = label;
  return label;
}

function iosTick(): void {
  iosSwitchElement()?.click();
}

/** Fire tactile feedback for a game event, if the platform supports it. */
export function haptic(kind: HapticKind): void {
  if (canVibrate()) {
    navigator.vibrate(PATTERNS[kind]);
    return;
  }
  // iOS fallback: one fixed light tick. Repeat it for a loss so the failure
  // reads as heavier than a flag placement.
  iosTick();
  if (kind === "lose" && typeof setTimeout === "function") {
    setTimeout(iosTick, 90);
    setTimeout(iosTick, 180);
  }
}
