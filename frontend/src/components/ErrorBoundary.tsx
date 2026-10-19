import { Component, type ErrorInfo, type ReactNode } from "react";
import { BrandMark } from "../brand/BrandMark";
import i18n from "../i18n";
import { Button, EmptyState } from "./ui";

type State = { error: Error | null };

/**
 * Last line of defence: a render error anywhere shows a recoverable screen
 * instead of a blank page. Uses the i18n instance directly since hooks
 * aren't available in class components.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="boot-splash">
        <EmptyState
          icon={<BrandMark size={28} />}
          title={i18n.t("crashTitle", { ns: "common" })}
          description={i18n.t("crashDescription", { ns: "common" })}
          action={<Button onClick={() => window.location.assign("/")}>{i18n.t("reloadApp", { ns: "common" })}</Button>}
        />
      </div>
    );
  }
}
