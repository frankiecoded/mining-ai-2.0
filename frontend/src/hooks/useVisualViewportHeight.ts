import { useEffect } from 'react';

/**
 * Keeps the document height in sync with the viewport that is actually visible.
 *
 * On iOS Safari the layout viewport (and therefore `height: 100%`) does not
 * shrink when the virtual keyboard opens, so bottom-anchored surfaces (the
 * composer dock, tab bar) get pushed underneath the keyboard. Listening to
 * `visualViewport` and mirroring its height onto the root element re-flows the
 * app into the visible area so those surfaces stay reachable.
 */
export function useVisualViewportHeight() {
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    const setHeight = () => {
      document.documentElement.style.height = `${vv.height}px`;
      if (window.scrollY !== 0 && (vv.offsetTop !== 0 || vv.offsetLeft !== 0)) {
        window.scrollTo({ top: vv.offsetTop, left: vv.offsetLeft });
      }
    };

    setHeight();
    vv.addEventListener('resize', setHeight);
    vv.addEventListener('scroll', setHeight);
    window.addEventListener('orientationchange', setHeight);
    return () => {
      vv.removeEventListener('resize', setHeight);
      vv.removeEventListener('scroll', setHeight);
      window.removeEventListener('orientationchange', setHeight);
      document.documentElement.style.height = '';
    };
  }, []);
}