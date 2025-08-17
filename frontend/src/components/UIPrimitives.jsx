export function Card({ children, className = '' }) {
  // add min-w-0 and overflow-hidden so long children can't force horizontal scroll
  return (
    <div className={`rounded-2xl bg-white/90 p-6 shadow-xl ring-1 ring-black/5 backdrop-blur min-w-0 w-full overflow-hidden ${className}`}>
      {children}
    </div>
  );
}
