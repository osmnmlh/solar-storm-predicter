import { RiskSnapshot } from "../services/api";

interface CombinedScenarioPanelProps {
  risk: RiskSnapshot | null;
}

export function CombinedScenarioPanel({ risk }: CombinedScenarioPanelProps) {
  if (!risk || !risk.combined_scenario) {
    return <p className="empty-state">Combined scenario analysis will appear after first full metric cycle.</p>;
  }

  const scenario = risk.combined_scenario;
  const bands = [risk.speed_band, risk.bz_band, risk.kp_band, risk.proton_band, risk.xray_band, risk.roti_band].filter(
    Boolean,
  );

  return (
    <div className="scenario-wrap reveal-rise">
      <div className={`scenario-banner scenario-${scenario.color}`}>
        <div>
          <p className="scenario-code">{scenario.code}</p>
          <h3>{scenario.name}</h3>
          <p>{scenario.analysis}</p>
        </div>
        <div className="scenario-meta">
          <span>Severity {risk.overall_severity}/5</span>
          <span>Signature: {risk.combination_signature ?? "n/a"}</span>
        </div>
      </div>

      <div className="band-grid">
        {bands.map((band) => (
          <article key={band!.metric} className={`band-card band-${band!.color}`}>
            <header>
              <strong>{band!.metric.toUpperCase()}</strong>
              <span>{band!.label}</span>
            </header>
            <p>{band!.description}</p>
          </article>
        ))}
      </div>

      <section className="scenario-lists">
        <div>
          <h4>Likely Issues</h4>
          <ul>
            {risk.likely_issues.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Recommended Actions</h4>
          <ul>
            {risk.recommended_actions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
