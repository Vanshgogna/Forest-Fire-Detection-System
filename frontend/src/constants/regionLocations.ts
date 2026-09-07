import type { RegionRisk } from "../types";

export const regionLocations: Record<
  string,
  Pick<RegionRisk, "id" | "name" | "state" | "coordinates"> & { timezone: string; coordinateMethod: string }
> = {
  r1: {
    id: "r1",
    name: "Bandipur Tiger Reserve",
    state: "Karnataka",
    coordinates: [11.667, 76.629],
    timezone: "Asia/Kolkata",
    coordinateMethod: "configured representative point"
  },
  r2: {
    id: "r2",
    name: "Simlipal Biosphere",
    state: "Odisha",
    coordinates: [21.594, 86.335],
    timezone: "Asia/Kolkata",
    coordinateMethod: "configured representative point"
  },
  r3: {
    id: "r3",
    name: "Gir Forest",
    state: "Gujarat",
    coordinates: [21.124, 70.824],
    timezone: "Asia/Kolkata",
    coordinateMethod: "configured representative point"
  },
  r4: {
    id: "r4",
    name: "Kaziranga Landscape",
    state: "Assam",
    coordinates: [26.577, 93.171],
    timezone: "Asia/Kolkata",
    coordinateMethod: "configured representative point"
  }
};
