// iOS Safari — and the game running as an installed full-screen PWA — ignore
// the viewport's `user-scalable=no`, so double-tapping still fires
// double-tap-to-zoom no matter what the meta tag says, and `touch-action` on
// the canvas does not reliably suppress it in standalone mode. A quick burst
// of taps in the same spot reads as repeated double-taps: the page zooms in,
// then out, and the viewport visibly jumps up and down. We cancel the gesture
// at the source.
//
// A double-tap is two taps close in *both* time and space, so that is exactly
// what we veto: a `touchend` within 300ms and 40px of the previous one is the
// second tap of a double-tap, and preventing its default stops the zoom. The
// first tap of any pair is never touched, and taps that land far apart (rapid
// reveals across different cells) are left alone — iOS does not zoom on those
// anyway — so ordinary play, including a fast run of single taps, is
// unaffected. Pointer events (which drive board taps) still fire either way;
// only the second tap's compat `click` is suppressed, which is the zoom we
// mean to kill. The `gesturestart` guard does the same for pinch-zoom.

export function preventDoubleTapZoom(): () => void {
  let lastTime = 0;
  let lastX = 0;
  let lastY = 0;

  const onTouchEnd = (e: TouchEvent) => {
    const t = e.changedTouches[0];
    if (!t) return;
    const dt = e.timeStamp - lastTime;
    const near = Math.hypot(t.clientX - lastX, t.clientY - lastY) < 40;
    if (dt > 0 && dt <= 300 && near) e.preventDefault();
    lastTime = e.timeStamp;
    lastX = t.clientX;
    lastY = t.clientY;
  };

  const onGesture = (e: Event) => e.preventDefault(); // pinch-zoom (iOS only)

  document.addEventListener("touchend", onTouchEnd, { passive: false });
  document.addEventListener("gesturestart", onGesture, { passive: false });

  return () => {
    document.removeEventListener("touchend", onTouchEnd);
    document.removeEventListener("gesturestart", onGesture);
  };
}
