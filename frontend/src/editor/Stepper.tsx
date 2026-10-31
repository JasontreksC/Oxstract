import { Check, Lock } from "lucide-react";
import { Link } from "react-router";
import { STEPS, type StepId } from "./steps";
import s from "./Stepper.module.css";

export interface StepperProps {
  projectId: string;
  current: StepId;
  locked: Record<StepId, string | null>;
}

export function Stepper({ projectId, current, locked }: StepperProps) {
  const currentIndex = STEPS.findIndex((step) => step.id === current);
  return (
    <nav aria-label="편집 단계" className={s.stepper}>
      <ol className={s.list}>
        {STEPS.map((step, index) => {
          const reason = locked[step.id];
          const isCurrent = index === currentIndex;
          const done = index < currentIndex && !reason;
          return (
            <li key={step.id} className={s.item}>
              {index > 0 ? <span className={s.connector} aria-hidden="true" /> : null}
              {reason ? (
                <span className={s.step} data-state="locked" title={reason}>
                  <span className={s.dot}>
                    <Lock size={12} aria-hidden="true" />
                  </span>
                  {step.label}
                  <span className="sr-only">(잠김: {reason})</span>
                </span>
              ) : (
                <Link
                  to={`/p/${projectId}/${step.id}`}
                  className={s.step}
                  data-state={isCurrent ? "current" : done ? "done" : "todo"}
                  aria-current={isCurrent ? "step" : undefined}
                >
                  <span className={s.dot}>
                    {done ? <Check size={14} strokeWidth={3} aria-hidden="true" /> : index + 1}
                  </span>
                  {step.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
