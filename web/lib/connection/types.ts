export type ConnectionDiagnosis = {
  apiBase: string;
  healthReachable: boolean;
  corsOk: boolean;
  /** True when the configured base fails health but another candidate succeeds */
  alternateReachable: boolean;
  suggestedApiBase?: string;
  error?: string;
};
