import { useEffect, useRef } from 'react';

/**
 * Returns focus to whatever opened a transient layer once that layer closes.
 *
 * The element that had focus when the layer opened is remembered, so focus lands back where
 * the person left it rather than at the top of the document. A caller that already holds an
 * explicit trigger ref should pass it as `trigger`: an explicit reference survives the layer
 * re-rendering its own trigger, which a captured `activeElement` cannot always do.
 *
 * Nothing is restored on first render, and nothing is restored to an element that has since
 * left the document.
 */
export function useFocusReturn(open: boolean, trigger?: { current: HTMLElement | null }) {
  const opener = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open) {
      if (!wasOpen.current) {
        opener.current = trigger?.current ?? (document.activeElement as HTMLElement | null);
      }
      wasOpen.current = true;
      return;
    }
    if (!wasOpen.current) return;
    wasOpen.current = false;
    const target = trigger?.current ?? opener.current;
    if (target && target.isConnected) target.focus();
    opener.current = null;
  }, [open, trigger]);
}
