import type { ReactNode } from "react";

export default function Modal({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: 16,
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        className="ef-card"
        style={{ width: "min(900px, 100%)", padding: 16 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
            gap: 12,
          }}
        >
          <h2 className="ef-title" style={{ fontSize: 20, margin: 0 }}>
            {title}
          </h2>

          <button className="ef-btn" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}