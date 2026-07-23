import { useEffect } from "react";
import "./Toast.css";

interface ToastProps {
  message: string;
  onDismiss: () => void;
}

/** A brief confirmation that fades itself out. The parent remounts it (via a
 * changing key) for each new message, so the timer always starts fresh. */
export default function Toast({ message, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3200);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="toast" role="status" aria-live="polite">
      {message}
    </div>
  );
}
