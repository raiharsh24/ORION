import React from 'react';

export const ExecutionReactorOverlay: React.FC = () => {
  // Bounding box size for targeting corners (e.g. at 68 and 432 px coordinates)
  const xMin = 68;
  const xMax = 432;
  const yMin = 68;
  const yMax = 432;
  const len = 22;

  // Render a set of 12 tiny ticks distributed along the outer ring
  const ticks = Array.from({ length: 12 });

  return (
    <div className="absolute inset-0 pointer-events-none select-none z-10 w-full h-full">
      <svg viewBox="0 0 500 500" className="w-full h-full">
        <defs>
          {/* Laser scanning sweep gradient */}
          <linearGradient id="sweepGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.38" />
            <stop offset="45%" stopColor="#00f2fe" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#00f2fe" stopOpacity="0" />
          </linearGradient>
          
          {/* Subtle grid pattern for targeting backdrop */}
          <pattern id="hudGrid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(0, 242, 254, 0.015)" strokeWidth="0.5" />
          </pattern>
        </defs>

        {/* Cinematic Grid Backdrop */}
        <rect width="100%" height="100%" fill="url(#hudGrid)" />

        {/* 1. Targeting L-Brackets */}
        <g opacity="0.6">
          {/* Top-Left */}
          <path d={`M ${xMin + len},${yMin} L ${xMin},${yMin} L ${xMin},${yMin + len}`} fill="none" stroke="#00f2fe" strokeWidth="1.2" />
          {/* Top-Right */}
          <path d={`M ${xMax - len},${yMin} L ${xMax},${yMin} L ${xMax},${yMin + len}`} fill="none" stroke="#00f2fe" strokeWidth="1.2" />
          {/* Bottom-Left */}
          <path d={`M ${xMin + len},${yMax} L ${xMin},${yMax} L ${xMin},${yMax - len}`} fill="none" stroke="#00f2fe" strokeWidth="1.2" />
          {/* Bottom-Right */}
          <path d={`M ${xMax - len},${yMax} L ${xMax},${yMax} L ${xMax},${yMax - len}`} fill="none" stroke="#00f2fe" strokeWidth="1.2" />
        </g>

        {/* 2. Rotating Mechanical HUD Circles */}
        {/* Inner Dotted HUD Ring */}
        <circle 
          cx="250" cy="250" r="148" 
          stroke="rgba(0, 242, 254, 0.22)" strokeWidth="1" 
          strokeDasharray="2, 6" fill="none" 
          className="animate-[spin_40s_linear_infinite]" 
          style={{ transformOrigin: 'center' }}
        />
        
        {/* Middle Segmented/Dashed HUD Ring (Opposite rotation) */}
        <circle 
          cx="250" cy="250" r="212" 
          stroke="rgba(0, 242, 254, 0.12)" strokeWidth="1.5" 
          strokeDasharray="20, 8" fill="none" 
          className="animate-[spin_60s_linear_infinite_reverse]" 
          style={{ transformOrigin: 'center' }}
        />

        {/* Outer Fine HUD Border with Orbit Markers */}
        <circle 
          cx="250" cy="250" r="236" 
          stroke="rgba(0, 242, 254, 0.05)" strokeWidth="0.8" 
          fill="none" 
        />
        
        {/* Orbit Marker Dot */}
        <circle 
          cx="250" cy="14" r="2.5" 
          fill="#00f2fe" 
          className="animate-[spin_12s_linear_infinite]"
          style={{ transformOrigin: 'center', filter: 'drop-shadow(0 0 3px #00f2fe)' }}
        />

        {/* 3. Laser Sweep Scan Overlay */}
        <circle 
          cx="250" cy="250" r="206" 
          stroke="url(#sweepGrad)" strokeWidth="2.5" 
          fill="none" 
          className="animate-[spin_9s_linear_infinite]" 
          style={{ transformOrigin: 'center' }}
        />

        {/* 4. Angle Ticks HUD Markers */}
        <g opacity="0.3">
          {ticks.map((_, i) => {
            const angle = (i * 360) / ticks.length;
            return (
              <line
                key={i}
                x1="250"
                y1="28"
                x2="250"
                y2="34"
                stroke="#00f2fe"
                strokeWidth="1.0"
                transform={`rotate(${angle} 250 250)`}
              />
            );
          })}
        </g>

        {/* 5. Faint Cybermatic circuit traces in corners */}
        <g stroke="rgba(0, 242, 254, 0.06)" strokeWidth="0.8" fill="none" opacity="0.7">
          <path d="M 30,80 L 50,80 L 70,60" />
          <path d="M 470,80 L 450,80 L 430,60" />
          <path d="M 30,420 L 50,420 L 70,440" />
          <path d="M 470,420 L 450,420 L 430,440" />
        </g>

        {/* 6. Cinematic Tiny Blinking Stars */}
        <g fill="#9bf6ff">
          <circle cx="45" cy="120" r="0.8" className="animate-pulse" />
          <circle cx="82" cy="380" r="0.8" className="animate-pulse" style={{ animationDelay: '0.5s' }} />
          <circle cx="420" cy="160" r="0.6" className="animate-pulse" style={{ animationDelay: '1.2s' }} />
          <circle cx="390" cy="390" r="1.0" className="animate-pulse" style={{ animationDelay: '0.8s' }} />
        </g>
      </svg>
    </div>
  );
};
export default ExecutionReactorOverlay;
