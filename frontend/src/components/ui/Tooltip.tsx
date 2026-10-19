import type { ReactNode } from "react";
import { Tooltip as RadixTooltip } from "radix-ui";
import "./Tooltip.css";

/** Mount once near the app root so tooltips share one open/close delay. */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return <RadixTooltip.Provider delayDuration={300}>{children}</RadixTooltip.Provider>;
}

/**
 * Hover/focus hint. `children` must be a single focusable element (it's used
 * via asChild), e.g. a Button or IconButton.
 */
export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content className="tooltip" side={side} sideOffset={6}>
          {content}
          <RadixTooltip.Arrow className="tooltip__arrow" />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
