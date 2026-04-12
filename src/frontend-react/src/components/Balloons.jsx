import { forwardRef, useRef, useCallback, useImperativeHandle } from 'react';
import { balloons, textBalloons } from 'balloons-js';

/**
 * Balloons — wrapper around balloons-js for confetti-like balloon effects.
 *
 * Usage (imperative):
 *   const ref = useRef(null);
 *   <Balloons ref={ref} type="default" />
 *   // later:
 *   ref.current?.launch();
 *
 * Props:
 *   type     — 'default' | 'text'
 *   text     — text to display (only when type === 'text')
 *   fontSize — font size for text balloons (default 120)
 *   color    — color for text balloons (default '#F59E0B')
 *   onLaunch — optional callback fired after animation starts
 */
const Balloons = forwardRef(({ type = 'default', text, fontSize = 120, color = '#F59E0B', onLaunch }, ref) => {
  const containerRef = useRef(null);

  const launch = useCallback(() => {
    if (type === 'default') {
      balloons();
    } else if (type === 'text' && text) {
      textBalloons([{ text, fontSize, color }]);
    }
    onLaunch?.();
  }, [type, text, fontSize, color, onLaunch]);

  useImperativeHandle(ref, () => ({ launch }), [launch]);

  // Render nothing — the balloons-js library manipulates the DOM directly
  return <div ref={containerRef} style={{ display: 'none' }} />;
});

Balloons.displayName = 'Balloons';
export { Balloons };
