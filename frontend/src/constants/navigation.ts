import {
  Activity,
  AlertTriangle,
  BarChart3,
  CloudSun,
  Flame,
  Home,
  Info,
  Leaf,
  Map,
  Radar,
  Settings
} from "lucide-react";

export const navigationItems = [
  { label: "Dashboard", href: "/dashboard", icon: Home },
  { label: "GIS Map", href: "/map", icon: Map },
  { label: "Vegetation", href: "/vegetation", icon: Leaf },
  { label: "Fire Hotspots", href: "/hotspots", icon: Flame },
  { label: "Weather", href: "/weather", icon: CloudSun },
  { label: "Predictions", href: "/prediction", icon: Radar },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Alerts", href: "/alerts", icon: AlertTriangle },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "About", href: "/about", icon: Info },
  { label: "System", href: "/dashboard", icon: Activity }
];
