export default function RabeliaLogo({ size = 'md' }) {
  const dims = size === 'lg'
    ? { box: 36, fs: 14, name: 16, sub: 11 }
    : size === 'sm'
    ? { box: 24, fs: 10, name: 13, sub: 10 }
    : { box: 28, fs: 11, name: 14, sub: 10 };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div className="rb-mono" style={{ width: dims.box, height: dims.box, fontSize: dims.fs }}>RB</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, lineHeight: 1.1 }}>
        <span style={{ fontWeight: 600, fontSize: dims.name, letterSpacing: '0.01em' }}>RABELIA</span>
        <span style={{ fontSize: dims.sub, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          Assistant documentaire
        </span>
      </div>
    </div>
  );
}
