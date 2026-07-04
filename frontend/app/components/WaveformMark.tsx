export function WaveformMark({ className = "" }: { className?: string }) {
  // Left half: audio waveform bars (uneven heights, like a real recording).
  // Right half: the same rhythm resolved into three flat outline rules.
  // The story: spoken words go in messy, come out structured.
  const bars = [4, 10, 6, 16, 8, 20, 11, 24, 9, 15, 6, 12, 5];

  return (
    <svg
      viewBox="0 0 360 64"
      className={className}
      role="img"
      aria-label="A waveform resolving into three structured lines"
    >
      {bars.map((h, i) => (
        <rect
          key={i}
          x={i * 12}
          y={32 - h / 2}
          width="5"
          height={h}
          rx="2.5"
          fill="#E8A33D"
          opacity={0.55 + (i / bars.length) * 0.45}
        />
      ))}
      <line x1="176" y1="32" x2="196" y2="32" stroke="#2C3444" strokeWidth="2" strokeDasharray="2 4" />
      <rect x="206" y="14" width="140" height="6" rx="3" fill="#7C7AFF" />
      <rect x="206" y="29" width="104" height="6" rx="3" fill="#3FA79A" />
      <rect x="206" y="44" width="120" height="6" rx="3" fill="#E8A33D" />
    </svg>
  );
}
