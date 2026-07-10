import type { Transition } from 'framer-motion';

/**
 * Single motion language for the Command Center. Every panel animation uses
 * these so timing, easing and feel stay consistent across the interface.
 */
export const CC_EASE = [0.22, 1, 0.36, 1] as const;

export const CC_TRANSITION: Transition = {
  duration: 0.45,
  ease: CC_EASE,
};

export const CC_TRANSITION_SLOW: Transition = {
  duration: 0.7,
  ease: CC_EASE,
};

/** Shared glow pulse used by synchronized highlights. */
export const CC_GLOW = '0 0 14px rgba(0, 242, 254, 0.35)';
