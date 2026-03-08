export default function Topbar() {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e5e5e5",
        borderRadius: 12,
        padding: "14px 18px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 16,
      }}
    >
      <div>
        <div style={{ fontWeight: 900, fontSize: 20 }}>EcoFit Municipal</div>
        <div style={{ fontSize: 13, opacity: 0.7 }}>Operations Dashboard</div>
      </div>

      <div style={{ fontSize: 14, opacity: 0.7 }}>Colombo • Municipal User</div>
    </div>
  );
}