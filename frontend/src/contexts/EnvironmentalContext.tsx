import { createContext, ReactNode, useContext, useMemo, useState } from "react";

interface EnvironmentalContextValue {
  selectedRegionId: string;
  setSelectedRegionId: (id: string) => void;
}

const EnvironmentalContext = createContext<EnvironmentalContextValue | undefined>(undefined);

export function EnvironmentalProvider({ children }: { children: ReactNode }) {
  const [selectedRegionId, setSelectedRegionId] = useState("r1");
  const value = useMemo(() => ({ selectedRegionId, setSelectedRegionId }), [selectedRegionId]);
  return <EnvironmentalContext.Provider value={value}>{children}</EnvironmentalContext.Provider>;
}

export function useEnvironmentalContext() {
  const context = useContext(EnvironmentalContext);
  if (!context) throw new Error("useEnvironmentalContext must be used within EnvironmentalProvider");
  return context;
}
