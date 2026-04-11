import React, { useState, useEffect, useRef } from 'react';
import { ArrowRight, Zap } from 'lucide-react';

/**
 * RadialOrbitalTimeline — adapted from TypeScript/shadcn original.
 * No shadcn, no TypeScript, styled with project tokens (#5ed29c, liquid-glass, etc.)
 *
 * Props:
 *   timelineData: Array<{
 *     id: number,
 *     title: string,
 *     date: string,
 *     content: string,
 *     icon: React.ElementType,
 *     relatedIds: number[],
 *     status: 'completed' | 'in-progress' | 'pending',
 *     energy: number   // 0-100, used for glow size and bar
 *   }>
 */
export default function RadialOrbitalTimeline({ timelineData }) {
  const [expandedItems, setExpandedItems] = useState({});
  const [rotationAngle, setRotationAngle] = useState(0);
  const [autoRotate, setAutoRotate] = useState(true);
  const [pulseEffect, setPulseEffect] = useState({});
  const [activeNodeId, setActiveNodeId] = useState(null);
  const containerRef = useRef(null);
  const orbitRef = useRef(null);
  const nodeRefs = useRef({});

  const handleContainerClick = (e) => {
    if (e.target === containerRef.current || e.target === orbitRef.current) {
      setExpandedItems({});
      setActiveNodeId(null);
      setPulseEffect({});
      setAutoRotate(true);
    }
  };

  const getRelatedItems = (itemId) => {
    const item = timelineData.find(i => i.id === itemId);
    return item ? item.relatedIds : [];
  };

  const toggleItem = (id) => {
    setExpandedItems(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(k => { if (parseInt(k) !== id) next[parseInt(k)] = false; });
      next[id] = !prev[id];

      if (!prev[id]) {
        setActiveNodeId(id);
        setAutoRotate(false);
        const pulse = {};
        getRelatedItems(id).forEach(relId => { pulse[relId] = true; });
        setPulseEffect(pulse);
      } else {
        setActiveNodeId(null);
        setAutoRotate(true);
        setPulseEffect({});
      }
      return next;
    });
  };

  useEffect(() => {
    if (!autoRotate) return;
    const timer = setInterval(() => {
      setRotationAngle(prev => Number(((prev + 0.3) % 360).toFixed(3)));
    }, 50);
    return () => clearInterval(timer);
  }, [autoRotate]);

  const calcPos = (index, total) => {
    const angle = ((index / total) * 360 + rotationAngle) % 360;
    const radius = 185;
    const rad = (angle * Math.PI) / 180;
    return {
      x: radius * Math.cos(rad),
      y: radius * Math.sin(rad),
      zIndex: Math.round(100 + 50 * Math.cos(rad)),
      opacity: Math.max(0.35, Math.min(1, 0.35 + 0.65 * ((1 + Math.sin(rad)) / 2))),
    };
  };

  const isRelated = (itemId) => activeNodeId ? getRelatedItems(activeNodeId).includes(itemId) : false;

  const statusStyle = (status) => {
    if (status === 'completed') return { color: '#5ed29c', background: 'rgba(94,210,156,0.08)', border: '1px solid rgba(94,210,156,0.25)' };
    if (status === 'in-progress') return { color: '#fbbf24', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)' };
    return { color: 'rgba(255,255,255,0.35)', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' };
  };

  const statusLabel = (s) => s === 'completed' ? 'Actif' : s === 'in-progress' ? 'En cours' : 'Inactif';

  return (
    <div
      ref={containerRef}
      onClick={handleContainerClick}
      className="w-full flex items-center justify-center overflow-visible"
      style={{ height: 500 }}
    >
      <div className="relative w-full max-w-4xl h-full flex items-center justify-center">
        <div
          ref={orbitRef}
          className="absolute w-full h-full flex items-center justify-center"
          style={{ perspective: '1000px' }}
        >
          {/* Center core */}
          <div
            className="absolute w-14 h-14 rounded-full flex items-center justify-center z-10 shrink-0"
            style={{ background: 'radial-gradient(circle, rgba(94,210,156,0.95) 0%, rgba(12,26,15,0.9) 100%)', boxShadow: '0 0 40px rgba(94,210,156,0.25)' }}
          >
            <div className="absolute w-20 h-20 rounded-full border border-[#5ed29c]/20 animate-ping opacity-40" />
            <div className="absolute w-28 h-28 rounded-full border border-[#5ed29c]/10 animate-ping opacity-20" style={{ animationDelay: '0.7s' }} />
            <div className="w-6 h-6 rounded-full bg-white/90" />
          </div>

          {/* Orbit ring */}
          <div className="absolute rounded-full border border-white/[0.05]" style={{ width: 390, height: 390 }} />

          {/* Nodes */}
          {timelineData.map((item, index) => {
            const pos = calcPos(index, timelineData.length);
            const expanded = !!expandedItems[item.id];
            const related = isRelated(item.id);
            const pulsing = !!pulseEffect[item.id];
            const Icon = item.icon;

            return (
              <div
                key={item.id}
                ref={el => (nodeRefs.current[item.id] = el)}
                className="absolute transition-all duration-700 cursor-pointer"
                style={{
                  transform: `translate(${pos.x}px, ${pos.y}px)`,
                  zIndex: expanded ? 200 : pos.zIndex,
                  opacity: expanded ? 1 : pos.opacity,
                }}
                onClick={e => { e.stopPropagation(); toggleItem(item.id); }}
              >
                {/* Energy halo */}
                <div
                  className={`absolute rounded-full ${pulsing ? 'animate-pulse' : ''}`}
                  style={{
                    background: 'radial-gradient(circle, rgba(94,210,156,0.12) 0%, transparent 70%)',
                    width: item.energy * 0.4 + 36,
                    height: item.energy * 0.4 + 36,
                    left: -((item.energy * 0.4 + 36 - 40) / 2),
                    top: -((item.energy * 0.4 + 36 - 40) / 2),
                  }}
                />

                {/* Node icon */}
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300"
                  style={{
                    background: expanded ? '#5ed29c' : related ? 'rgba(94,210,156,0.22)' : 'rgba(8,8,8,0.9)',
                    border: `2px solid ${expanded ? '#5ed29c' : related ? 'rgba(94,210,156,0.5)' : 'rgba(255,255,255,0.12)'}`,
                    color: expanded ? '#000' : '#fff',
                    transform: expanded ? 'scale(1.45)' : 'scale(1)',
                    boxShadow: expanded ? '0 0 22px rgba(94,210,156,0.5)' : related ? '0 0 10px rgba(94,210,156,0.2)' : 'none',
                  }}
                >
                  <Icon size={14} />
                </div>

                {/* Label */}
                <div
                  className="absolute whitespace-nowrap text-[9px] font-semibold uppercase tracking-[0.15em] transition-all duration-300"
                  style={{
                    top: expanded ? 48 : 42,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    color: expanded ? '#5ed29c' : 'rgba(255,255,255,0.45)',
                    textAlign: 'center',
                  }}
                >
                  {item.title}
                </div>

                {/* Expanded card */}
                {expanded && (
                  <div
                    className="absolute w-60 rounded-[18px] p-5 shadow-2xl"
                    style={{
                      top: 64,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      background: 'rgba(5,5,5,0.97)',
                      border: '1px solid rgba(94,210,156,0.18)',
                      backdropFilter: 'blur(24px)',
                    }}
                  >
                    {/* connector */}
                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-px h-2 bg-[#5ed29c]/30" />

                    <div className="flex justify-between items-center mb-3">
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                        style={statusStyle(item.status)}
                      >
                        {statusLabel(item.status)}
                      </span>
                      <span className="text-[9px] text-white/25 font-mono tracking-wider">{item.date}</span>
                    </div>

                    <h4 className="text-[13px] font-semibold text-white mb-1.5">{item.title}</h4>
                    <p className="text-[11px] text-white/50 leading-relaxed mb-4">{item.content}</p>

                    {/* Energy bar */}
                    <div>
                      <div className="flex justify-between text-[9px] mb-1">
                        <span className="flex items-center gap-1 text-white/25"><Zap size={8} />Fiabilité</span>
                        <span className="text-white/40 font-mono">{item.energy}%</span>
                      </div>
                      <div className="w-full h-0.5 bg-white/[0.05] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${item.energy}%`, background: 'linear-gradient(to right, #5ed29c, rgba(94,210,156,0.3))' }}
                        />
                      </div>
                    </div>

                    {/* Related nodes */}
                    {item.relatedIds.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-white/[0.05]">
                        <div className="text-[8px] text-white/20 uppercase tracking-widest mb-2">Connecté à</div>
                        <div className="flex flex-wrap gap-1">
                          {item.relatedIds.map(relId => {
                            const rel = timelineData.find(i => i.id === relId);
                            return (
                              <button
                                key={relId}
                                onClick={e => { e.stopPropagation(); toggleItem(relId); }}
                                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] border border-white/[0.08] text-white/40 hover:text-[#5ed29c] hover:border-[#5ed29c]/25 transition-all"
                                style={{ background: 'rgba(255,255,255,0.02)' }}
                              >
                                {rel?.title} <ArrowRight size={7} />
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
