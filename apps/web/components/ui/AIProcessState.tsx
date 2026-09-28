// Design-system component. A staged "here's what's actually happening"
// checklist for a meaningful AI process (specs/003-premium-uiux-redesign
// sections 13 "End Interview Experience" and 29 "Loading States") - never a
// giant spinner, never a faked progress percentage. Each step is
// "done" | "active" | "pending"; render order is the argument order.
export interface ProcessStep {
  label: string;
  status: "done" | "active" | "pending";
}

function StepIcon({ status }: { status: ProcessStep["status"] }) {
  if (status === "done") {
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-status-positive text-[10px] text-white dark:text-neutral-950">
        &#10003;
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute h-4 w-4 animate-ping rounded-full bg-accent/40" />
        <span className="relative h-2 w-2 rounded-full bg-accent" />
      </span>
    );
  }
  return <span className="h-4 w-4 shrink-0 rounded-full border border-border" />;
}

export default function AIProcessState({ title, steps }: { title?: string; steps: ProcessStep[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      {title && <p className="mb-3 text-sm font-semibold text-foreground">{title}</p>}
      <ul className="space-y-2.5">
        {steps.map((step) => (
          <li key={step.label} className="flex items-center gap-2.5">
            <StepIcon status={step.status} />
            <span
              className={
                "text-sm " +
                (step.status === "pending" ? "text-muted-foreground" : "text-foreground")
              }
            >
              {step.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
