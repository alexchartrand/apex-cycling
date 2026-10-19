import { createContext, useContext, type ReactNode } from "react";

export type ToastInput = {
  title: ReactNode;
  description?: ReactNode;
  tone?: "info" | "success" | "error";
};

export const ToastContext = createContext<{ toast: (input: ToastInput) => void } | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
