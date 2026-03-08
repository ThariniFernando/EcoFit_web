import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function PageFrame({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", background: "#f6f7f9", padding: 16 }}>
      <div style={{ maxWidth: 1500, margin: "0 auto" }}>
        <Topbar />

        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>
          <aside>
            <Sidebar />
          </aside>

          <main>{children}</main>
        </div>
      </div>
    </div>
  );
}