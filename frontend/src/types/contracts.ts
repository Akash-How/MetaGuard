export type ModuleStatus = "stub" | "in-progress" | "done";

export type FeatureCard = {
  id: string;
  name: string;
  status: ModuleStatus;
  summary: string;
};

