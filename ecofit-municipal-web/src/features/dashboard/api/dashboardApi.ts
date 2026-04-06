import { apiClient } from "../../../lib/apiClient";

export type DashboardStats = {
  riskCounts: {
    EMERGENCY: number;
    HIGH: number;
    MEDIUM: number;
    LOW: number;
    TOTAL: number;
  };
  tsPrediction: string | null;
  topRiskWards: Array<{
    wardId: string;
    wardName: string;
    riskClass: string;
    riskScore: number;
  }>;
  complaints: {
    total: number;
    NEW: number;
    IN_PROGRESS: number;
    RESOLVED: number;
    REJECTED: number;
  };
  serviceLogs: {
    total: number;
    collected: number;
    missed: number;
    partial: number;
  };
  openAlerts: number;
};

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const [predictionsRes, complaintsRes, serviceLogsRes, alertsRes] =
    await Promise.all([
      apiClient.get("/api/v1/predictions/latest?limit=100"),
      apiClient.get("/api/v1/complaints?hours=168&limit=200"),
      apiClient.get("/api/v1/service-logs/live?hours=168"),
      apiClient.get("/api/v1/alerts/latest?limit=200"),
    ]);

  // Predictions
  const predictions = predictionsRes.data;
  const riskCounts = predictions.counts || {
    EMERGENCY: 0, HIGH: 0, MEDIUM: 0, LOW: 0, TOTAL: 0,
  };
  const items = predictions.items || [];
  const topRiskWards = [...items]
    .sort((a: any, b: any) => b.riskScore - a.riskScore)
    .slice(0, 5)
    .map((w: any) => ({
      wardId: w.wardId,
      wardName: w.wardName || w.wardId,
      riskClass: w.riskClass,
      riskScore: w.riskScore,
    }));

  // Complaints
  const complaintItems: any[] = complaintsRes.data?.items || [];
  const complaints = {
    total: complaintsRes.data?.total || complaintItems.length,
    NEW: complaintItems.filter((c) =>
      ["NEW", "OPEN", "PENDING"].includes(String(c.status).toUpperCase())
    ).length,
    IN_PROGRESS: complaintItems.filter((c) =>
      String(c.status).toUpperCase() === "IN_PROGRESS"
    ).length,
    RESOLVED: complaintItems.filter((c) =>
      ["RESOLVED", "DONE", "CLOSED"].includes(String(c.status).toUpperCase())
    ).length,
    REJECTED: complaintItems.filter((c) =>
      String(c.status).toUpperCase() === "REJECTED"
    ).length,
  };

  // Service logs
  const logs: any[] = Array.isArray(serviceLogsRes.data)
    ? serviceLogsRes.data
    : [];
  const serviceLogs = {
    total: logs.length,
    collected: logs.filter((l) =>
      String(l.outcome || l.status || "").toUpperCase().includes("COLLECT")
    ).length,
    missed: logs.filter((l) =>
      String(l.outcome || l.status || "").toUpperCase().includes("MISS")
    ).length,
    partial: logs.filter((l) =>
      String(l.outcome || l.status || "").toUpperCase().includes("PART")
    ).length,
  };

  // Alerts
  const alerts: any[] = Array.isArray(alertsRes.data) ? alertsRes.data : [];
  const openAlerts = alerts.filter(
    (a) => String(a.status).toUpperCase() === "OPEN"
  ).length;

  return {
    riskCounts,
    tsPrediction: predictions.tsPrediction || null,
    topRiskWards,
    complaints,
    serviceLogs,
    openAlerts,
  };
}