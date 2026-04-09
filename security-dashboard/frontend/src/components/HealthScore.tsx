// Hero metric: single fleet health score as a large, color-coded number.
// Green above 90%, yellow 75-90%, red below 75%. This is the number a
// CISO glances at in a weekly report. Fleet doesn't provide it because
// Fleet treats all policy failures equally.

interface Props {
  score: number;
  deviceCount: number;
  totalChecks: number;
}

function scoreColor(score: number): string {
  if (score >= 90) return "text-green-600";
  if (score >= 75) return "text-severity-medium";
  return "text-severity-critical";
}

function scoreBand(score: number): string {
  if (score >= 90) return "Healthy";
  if (score >= 75) return "Needs attention";
  return "Critical";
}

export default function HealthScore({ score, deviceCount, totalChecks }: Props) {
  return (
    <div className="card px-6 py-6 flex flex-col items-center justify-center text-center">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2">
        Fleet Health Score
      </p>
      <p className={`text-[56px] leading-none font-bold ${scoreColor(score)}`}>
        {score}%
      </p>
      <p className={`mt-1 text-[13px] font-medium ${scoreColor(score)}`}>
        {scoreBand(score)}
      </p>
      <div className="mt-4 flex gap-6 text-[12px] text-neutral-500">
        <span>{deviceCount} devices</span>
        <span>{totalChecks.toLocaleString()} checks</span>
      </div>
      <p className="mt-3 text-[11px] text-neutral-300 leading-snug max-w-[220px]">
        Weighted by severity: critical failures count 4x, low count 1x
      </p>
    </div>
  );
}
