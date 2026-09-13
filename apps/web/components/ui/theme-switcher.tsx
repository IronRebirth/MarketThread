"use client";

import { useTheme } from "./theme-provider";

const themes = [
  { value: "light" as const, label: "Light" },
  { value: "dark" as const, label: "Dark" },
  { value: "system" as const, label: "System" },
];

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className="inline-flex items-center rounded-md border border-border bg-surface p-1 shadow-sm"
      role="group"
      aria-label="Theme preference"
    >
      {themes.map((option) => {
        const isSelected = theme === option.value;

        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isSelected}
            onClick={() => setTheme(option.value)}
            className={[
              "rounded px-3 py-1.5 text-xs font-medium transition-colors",
              isSelected
                ? "bg-brand text-text-inverse"
                : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}