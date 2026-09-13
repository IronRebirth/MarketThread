import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({
  label,
  error,
  id,
  className = "",
  ...props
}: InputProps) {
  const generatedId = id ?? "marketthread-input";

  return (
    <div className="flex w-full flex-col gap-1.5">
      {label && (
        <label
          htmlFor={generatedId}
          className="text-sm font-medium text-text-primary"
        >
          {label}
        </label>
      )}

      <input
        id={generatedId}
        className={[
          "min-h-10 w-full rounded-md border bg-surface px-3 py-2",
          "text-sm text-text-primary placeholder:text-text-muted",
          "border-border-strong",
          "transition-colors",
          "focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20",
          "disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60",
          error ? "border-negative focus:border-negative focus:ring-negative/20" : "",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${generatedId}-error` : undefined}
        {...props}
      />

      {error && (
        <p
          id={`${generatedId}-error`}
          className="text-xs text-negative"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}