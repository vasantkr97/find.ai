import { cn } from "@/lib/utils";
import { forwardRef, type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none cursor-pointer",
          {
            "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] active:bg-indigo-700 shadow-lg shadow-indigo-500/10":
              variant === "primary",
            "bg-[var(--color-card)] text-[var(--color-text)] hover:bg-[var(--color-card-hover)] border border-[var(--color-border)]":
              variant === "secondary",
            "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-card)]":
              variant === "ghost",
            "bg-red-600/10 text-red-400 hover:bg-red-600/20 border border-red-500/20":
              variant === "danger",
          },
          {
            "text-xs px-2.5 py-1.5": size === "sm",
            "text-sm px-4 py-2": size === "md",
            "text-base px-6 py-3": size === "lg",
          },
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button };
