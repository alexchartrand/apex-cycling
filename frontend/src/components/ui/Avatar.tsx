import { initialsOf } from "./initials";
import "./Avatar.css";

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`avatar avatar--${size}`} aria-hidden>
      {initialsOf(name)}
    </span>
  );
}
