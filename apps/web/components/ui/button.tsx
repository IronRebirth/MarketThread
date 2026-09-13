import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-white shadow-sm hover:bg-brand-hover focus-visible:ring-2 focus-visible:ring-brand",
  secondary:
    "border border-border-strong bg-surface text-text-primary shadow-sm hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-brand",
  ghost:
    "bg-transparent text-text-secondary hover:bg-surface-muted hover:text-text-primary focus-visible:ring-2 focus-visible:ring-brand",
  danger:
    "bg-negative text-white shadow-sm hover:opacity-90 focus-visible:ring-2 focus-visible:ring-negative",
};

export function Button({
  variant = "primary",
  fullWidth = false,
  className = "",
  type = "button",
  disabled,
  ...props
}: ButtonProps) {
  const widthClass = fullWidth ? "w-full" : "";

  return (
    <button
      type={type}
      disabled={disabled}
      className={[
        "inline-flex min-h-10 items-center justify-center rounded-md px-4 py-2",
        "text-sm font-medium transition-colors duration-150",
        "disabled:pointer-events-none disabled:opacity-50",
        variantClasses[variant],
        widthClass,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    />
  );
}