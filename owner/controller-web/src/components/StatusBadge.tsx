import { Badge } from "./ui/Badge";
import { statusMessageKey, useT } from "../i18n";

const STATUS_CLASSES: Record<string, string> = {
  active: "border-primary bg-primary text-primary-foreground",
  grace: "border-accent bg-accent text-accent-foreground",
  suspended: "border-destructive bg-destructive text-destructive-foreground",
};

export function StatusBadge({ status, testId }: { status: string; testId?: string }) {
  const t = useT();
  return (
    <Badge className={STATUS_CLASSES[status] ?? ""} data-testid={testId}>
      {t(statusMessageKey(status))}
    </Badge>
  );
}
