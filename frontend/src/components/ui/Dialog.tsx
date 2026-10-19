import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Dialog as RadixDialog } from "radix-ui";
import "./Dialog.css";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  /** Buttons row, right-aligned on desktop, full-width stacked on phones. */
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  /**
   * "dialog" is a centered modal that becomes a bottom sheet on phones;
   * "sheet-right" slides in from the right on every screen size.
   */
  variant?: "dialog" | "sheet-right";
};

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
  variant = "dialog",
}: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="dialog__overlay" />
        <RadixDialog.Content
          className={`dialog dialog--${variant} dialog--${size}`}
          {...(description == null ? { "aria-describedby": undefined } : {})}
        >
          <header className="dialog__header">
            <div className="dialog__heading">
              <RadixDialog.Title className="dialog__title">{title}</RadixDialog.Title>
              {description != null && (
                <RadixDialog.Description className="dialog__description">{description}</RadixDialog.Description>
              )}
            </div>
            <RadixDialog.Close className="dialog__close" aria-label="Close">
              <X aria-hidden />
            </RadixDialog.Close>
          </header>
          {children != null && <div className="dialog__body">{children}</div>}
          {footer != null && <footer className="dialog__footer">{footer}</footer>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
