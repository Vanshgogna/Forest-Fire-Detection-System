import { Brain, Database, Globe2, Server } from "lucide-react";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";

export function AboutPage() {
  return (
    <>
      <PageHeader eyebrow="Project Details" title="FireSight AI Architecture" description="A portfolio-ready forest fire prediction platform built around GIS, remote sensing, weather intelligence, and explainable ML." />
      <Panel title="System Modules">
        <div className="feature-grid compact">
          {[
            ["Frontend", "React, TypeScript, Vite, charts, maps, dashboards", Globe2],
            ["Backend", "FastAPI REST services for environmental intelligence", Server],
            ["Data", "Satellite imagery, weather feeds, hotspot history", Database],
            ["AI", "Risk prediction, confidence scoring, recommendations", Brain]
          ].map(([title, text, Icon]) => (
            <article key={title as string}>
              <Icon size={24} />
              <h2>{title as string}</h2>
              <p>{text as string}</p>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
