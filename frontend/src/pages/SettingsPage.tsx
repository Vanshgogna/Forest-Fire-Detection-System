import { Bell, Moon, RefreshCcw, Shield } from "lucide-react";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";

export function SettingsPage() {
  return (
    <>
      <PageHeader eyebrow="Settings" title="Platform Preferences" description="Review the demo configuration currently used by FireSight AI." />
      <Panel title="Operational Settings" subtitle="Read-only configuration snapshot">
        <div className="settings-grid">
          {[
            ["Critical alert threshold", "Risk score above 85", Shield],
            ["Auto refresh", "Every 30 seconds", RefreshCcw],
            ["Theme", "Follows the current interface theme", Moon],
            ["Notifications", "In-app alert review only", Bell]
          ].map(([title, detail, Icon]) => (
            <article className="setting-row" key={title as string}>
              <Icon size={20} />
              <div><strong>{title as string}</strong><span>{detail as string}</span></div>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
