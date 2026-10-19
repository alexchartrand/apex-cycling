import { useCallback, useMemo, useState, type ReactNode } from "react";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { Toast as RadixToast } from "radix-ui";
import { ToastContext, type ToastInput } from "./useToast";
import "./Toast.css";

type ActiveToast = ToastInput & { id: number };

const TONE_ICONS = { info: Info, success: CircleCheck, error: CircleAlert };

let nextId = 1;

/** Mount once near the app root; components call `useToast()` to show one. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);

  const toast = useCallback((input: ToastInput) => {
    setToasts((current) => [...current, { ...input, id: nextId++ }]);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      <RadixToast.Provider swipeDirection="right" duration={5000}>
        {children}
        {toasts.map(({ id, title, description, tone = "info" }) => {
          const Icon = TONE_ICONS[tone];
          return (
            <RadixToast.Root
              key={id}
              className={`toast toast--${tone}`}
              type={tone === "error" ? "foreground" : "background"}
              onOpenChange={(open) => !open && remove(id)}
            >
              <Icon className="toast__icon" aria-hidden />
              <div className="toast__text">
                <RadixToast.Title className="toast__title">{title}</RadixToast.Title>
                {description != null && (
                  <RadixToast.Description className="toast__description">{description}</RadixToast.Description>
                )}
              </div>
              <RadixToast.Close className="toast__close" aria-label="Dismiss">
                <X aria-hidden />
              </RadixToast.Close>
            </RadixToast.Root>
          );
        })}
        <RadixToast.Viewport className="toast-viewport" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}
