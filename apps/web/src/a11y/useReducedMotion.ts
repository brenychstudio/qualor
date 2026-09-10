import { useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

/**
 * Projects the browser's reduced-motion preference into React state.
 *
 * It only reports what the person asked for. Motion itself stays in CSS, so honouring the
 * preference shortens or removes spatial transitions without changing any content, state or
 * timing that the workspace depends on.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia(QUERY).matches);
  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return reduced;
}
