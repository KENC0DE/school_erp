// Fixture for the UI gate self-test: a data screen that renders loading and
// error states but forgets the empty state. The gate must reject this file.
import { ErrorState, LoadingState } from "@erp/ui-web";

export function FixtureScreen({ rows }: { rows: string[] }) {
  if (rows.length > 0) return <LoadingState label="loading" />;
  return <ErrorState title="error" />;
}
