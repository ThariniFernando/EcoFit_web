export default function WeatherPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[rgb(var(--primary))]">Weather Hourly</h1>
        <p className="ef-subtitle mt-1">Debug view of weather_hourly collection</p>
      </div>

      <div className="ef-card p-6">
        <div className="ef-title">Weather Data</div>
        <p className="text-sm text-[rgb(var(--muted))] mt-1">
          We will show latest hourly records next.
        </p>
      </div>
    </div>
  );
}
