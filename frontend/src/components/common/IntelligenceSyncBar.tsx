import { Check, ChevronDown, Satellite } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useEnvironmentalContext } from "../../contexts/EnvironmentalContext";
import { ENVIRONMENTAL_QUERY_KEY, useEnvironmentalData } from "../../hooks/useEnvironmentalData";

export function IntelligenceSyncBar() {
  const { data, isFetching } = useEnvironmentalData();
  const { selectedRegionId, setSelectedRegionId } = useEnvironmentalContext();
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const regionPickerRef = useRef<HTMLDivElement>(null);
  const selectedRegion = data?.regions.find((region) => region.id === selectedRegionId) ?? data?.regions[0];

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!regionPickerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  function selectRegion(regionId: string) {
    setSelectedRegionId(regionId);
    setOpen(false);
    void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY });
  }

  if (!data) return null;
  return <section className="intelligence-sync" aria-label="Shared intelligence filters">
    <div className="sync-region" ref={regionPickerRef}>
      <Satellite size={16} />
      <span>Connected intelligence</span>
      <button
        className="region-picker-button"
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      >
        <strong>{selectedRegion?.name ?? "Select region"}</strong>
        <ChevronDown size={15} />
      </button>
      {open ? (
        <div className="region-picker-menu" role="listbox" aria-label="Available regions">
          {data.regions.map((region) => (
            <button
              key={region.id}
              type="button"
              role="option"
              aria-selected={region.id === selectedRegionId}
              className={region.id === selectedRegionId ? "active" : ""}
              onClick={() => selectRegion(region.id)}
            >
              <Check size={15} />
              <span>{region.name}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
    {isFetching ? <span className="sync-loading">Updating</span> : null}
  </section>;
}
