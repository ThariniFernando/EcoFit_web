import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "./layout/AppShell";

import SignInPage from "../features/auth/pages/SignInPage";
import SignUpPage from "../features/auth/pages/SignUpPage";

import RiskMapPage from "../features/predictions/pages/RiskMapPage";
import ActionPlanPage from "../features/operations/pages/ActionPlanPage";
import ServiceLogsPage from "../features/serviceLogs/pages/ServiceLogsPage";
import ComplaintsPage from "../features/complaints/pages/ComplaintsPage";
import WardHourlyFeaturesPage from "../features/wardHourlyFeatures/pages/WardHourlyFeaturesPage";
import WeatherPage from "../features/weather/pages/WeatherPage";
import KnowledgeBasePage from "../features/knowledgeBase/KnowledgeBasePage";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/sign-in" replace /> },

  { path: "/sign-in", element: <SignInPage /> },
  { path: "/sign-up", element: <SignUpPage /> },

  {
    path: "/",
    element: <AppShell />,
    children: [
      { path: "risk-map", element: <RiskMapPage /> },
      { path: "action-plan", element: <ActionPlanPage /> },
      { path: "service-logs", element: <ServiceLogsPage /> },
      { path: "complaints", element: <ComplaintsPage /> },
      { path: "ward-hourly-features", element: <WardHourlyFeaturesPage /> },
      { path: "weather-hourly", element: <WeatherPage /> },
      { path: "knowledge-base", element: <KnowledgeBasePage /> },
    ],
  },

  { path: "*", element: <Navigate to="/sign-in" replace /> },
]);