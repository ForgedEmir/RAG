import { motion } from 'framer-motion';

/**
 * ShiningText — shimmer/sweep animation over text.
 * Props:
 *   text      — string to display
 *   className — optional extra classes
 *   tag       — HTML tag to render ('span' | 'p' | 'h1' etc.), default 'span'
 */
export function ShiningText({ text, className = '', tag = 'span' }) {
  return (
    <motion.span
      className={`inline-block bg-[linear-gradient(110deg,rgba(255,255,255,0.18),35%,rgba(255,255,255,0.85),50%,rgba(255,255,255,0.18),75%,rgba(255,255,255,0.18))] bg-[length:200%_100%] bg-clip-text text-transparent font-light tracking-widest uppercase text-[11px] ${className}`}
      initial={{ backgroundPosition: '200% 0' }}
      animate={{ backgroundPosition: '-200% 0' }}
      transition={{
        repeat: Infinity,
        duration: 2.2,
        ease: 'linear',
      }}
    >
      {text}
    </motion.span>
  );
}
