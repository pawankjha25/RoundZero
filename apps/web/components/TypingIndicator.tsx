// Shown in the Interview Room while waiting on the interviewer's next turn -
// there was previously no loading state at all during that gap.
export default function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="Interviewer is composing a response">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
