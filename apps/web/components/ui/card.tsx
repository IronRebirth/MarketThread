import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  children: ReactNode;
}

export function Card({
  title,
  description,
  children,
  className = "",
  ...props
}: CardProps) {
  return (
    <section
      className={[
        "rounded-lg border border-border bg-surface shadow-sm",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      {(title || description) && (
        <header className="border-b border-border px-5 py-4">
          {title && (
            <h2 className="text-base font-semibold text-text-primary">
              {title}
            </h2>
          )}

          {description && (
            <p className="mt-1 text-sm text-text-secondary">
              {description}
            </p>
          )}
        </header>
      )}

      <div className="p-5">{children}</div>
    </section>
  );
}