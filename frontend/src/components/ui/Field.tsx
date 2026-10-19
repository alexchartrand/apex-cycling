import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import "./Field.css";

type FieldChrome = {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  /** @deprecated kept until every screen is restyled (T1.6). */
  scale?: "sm" | "md";
  /** Trailing unit shown inside the control, e.g. "kg", "km/h". */
  suffix?: ReactNode;
};

/**
 * Shared label/hint/error wrapper. The control gets aria-describedby /
 * aria-invalid wired to the hint and error, so screen readers announce them.
 */
function FieldShell({
  id,
  label,
  hint,
  error,
  className,
  children,
}: {
  id: string;
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  if (label == null && hint == null && error == null) return <>{children}</>;
  return (
    <div className={["field", error != null && "field--invalid", className].filter(Boolean).join(" ")}>
      {label != null && (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      {children}
      {error != null ? (
        <p className="field__error" id={`${id}-error`} role="alert">
          {error}
        </p>
      ) : (
        hint != null && (
          <p className="field__hint" id={`${id}-hint`}>
            {hint}
          </p>
        )
      )}
    </div>
  );
}

function describedBy(id: string, hint: ReactNode, error: ReactNode): string | undefined {
  if (error != null) return `${id}-error`;
  if (hint != null) return `${id}-hint`;
  return undefined;
}

function controlClass(scale: "sm" | "md" | undefined, className: string | undefined) {
  return ["field__control", scale === "sm" && "field__control--sm", className].filter(Boolean).join(" ");
}

export function Input({ label, hint, error, scale, suffix, className, id, ...props }: InputHTMLAttributes<HTMLInputElement> & FieldChrome) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const input = (
    <input
      id={inputId}
      className={controlClass(scale, className)}
      aria-invalid={error != null || undefined}
      aria-describedby={describedBy(inputId, hint, error)}
      {...props}
    />
  );
  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error}>
      {suffix != null ? (
        <div className="field__affix">
          {input}
          <span className="field__suffix">{suffix}</span>
        </div>
      ) : (
        input
      )}
    </FieldShell>
  );
}

export function Select({ label, hint, error, scale, className, id, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldChrome) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <FieldShell id={selectId} label={label} hint={hint} error={error}>
      <select
        id={selectId}
        className={controlClass(scale, className)}
        aria-invalid={error != null || undefined}
        aria-describedby={describedBy(selectId, hint, error)}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export function Textarea({ label, hint, error, className, id, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldChrome) {
  const autoId = useId();
  const textareaId = id ?? autoId;
  return (
    <FieldShell id={textareaId} label={label} hint={hint} error={error}>
      <textarea
        id={textareaId}
        className={controlClass(undefined, className)}
        aria-invalid={error != null || undefined}
        aria-describedby={describedBy(textareaId, hint, error)}
        {...props}
      />
    </FieldShell>
  );
}

/** Checkbox with its label to the right, the common "remember me" layout. */
export function Checkbox({ label, className, id, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: ReactNode }) {
  const autoId = useId();
  const checkboxId = id ?? autoId;
  return (
    <label className={["field-check", className].filter(Boolean).join(" ")} htmlFor={checkboxId}>
      <input id={checkboxId} type="checkbox" {...props} />
      <span>{label}</span>
    </label>
  );
}
