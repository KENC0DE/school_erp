import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  DatePicker,
  EmptyState,
  Field,
  FormGrid,
  FormLayout,
  FormSection,
  FormSpan,
  Input,
  Page,
  PageHeader,
  SaveBar,
  Select,
  Tabs,
  Textarea,
  type Column,
} from "@erp/ui-web";
import { formatSantim } from "@erp/money";
import { useMemo, useState } from "react";

import { useI18n } from "../../providers/I18nProvider";

interface DemoRow {
  id: string;
  name: string;
  amharic: string;
  status: "active" | "pending";
  updated: string;
}

const ROWS: DemoRow[] = [
  { id: "1", name: "Abebe Kebede", amharic: "አበበ ከበደ", status: "active", updated: "2026-09-11" },
  { id: "2", name: "Hana Tesfaye", amharic: "ሃና ተስፋዬ", status: "pending", updated: "2026-09-12" },
  { id: "3", name: "Dawit Alemu", amharic: "ዳዊት አለሙ", status: "active", updated: "2026-09-14" },
];

export function DesignReferencePage() {
  return (
    <Page>
      <PageHeader title={<Title />} description={<Description />} />
      <Tabs
        items={[
          { key: "list", label: <TabLabel name="list" />, content: <ReferenceList /> },
          { key: "form", label: <TabLabel name="form" />, content: <ReferenceForm /> },
          { key: "dashboard", label: <TabLabel name="dashboard" />, content: <ReferenceDashboard /> },
        ]}
      />
    </Page>
  );
}

function Title() {
  const { t } = useI18n();
  return <>{t("design.title")}</>;
}

function Description() {
  const { t } = useI18n();
  return <>{t("design.description")}</>;
}

function TabLabel({ name }: { name: "list" | "form" | "dashboard" }) {
  const { t } = useI18n();
  return <>{t(`design.tabs.${name}`)}</>;
}

function ReferenceList() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [state, setState] = useState<"ready" | "loading" | "empty" | "error">("ready");

  const rows = useMemo(
    () =>
      ROWS.filter((row) => {
        const matchesSearch = `${row.name} ${row.amharic}`.toLowerCase().includes(search.toLowerCase());
        const matchesStatus = status === "all" || row.status === status;
        return matchesSearch && matchesStatus;
      }),
    [search, status],
  );

  const columns: Column<DemoRow>[] = [
    {
      key: "name",
      header: t("design.list.column.name"),
      sortable: true,
      render: (row) => (
        <div>
          <div className="font-medium">{row.name}</div>
          <div className="amharic text-muted-foreground">{row.amharic}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: t("design.list.column.status"),
      render: (row) => (
        <Badge variant={row.status === "active" ? "success" : "warning"}>
          {t(`design.status.${row.status}`)}
        </Badge>
      ),
    },
    {
      key: "updated",
      header: t("design.list.column.updated"),
      numeric: true,
      render: (row) => <span className="ui-num">{row.updated}</span>,
    },
  ];

  return (
    <div className="ui-page">
      <PageHeader
        level={2}
        title={t("design.list.title")}
        description={t("design.list.description")}
        actions={<Button>{t("design.list.add")}</Button>}
      />
      <Card>
        <CardContent>
          <div className="ui-form__grid">
            <Field label={t("design.filter.search")}>
              <Input value={search} onChange={(event) => setSearch(event.target.value)} />
            </Field>
            <Field label={t("design.filter.status")}>
              <Select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="all">{t("design.filter.all")}</option>
                <option value="active">{t("design.status.active")}</option>
                <option value="pending">{t("design.status.pending")}</option>
              </Select>
            </Field>
            <Field label={t("design.state")} hint={t("design.state.hint")}>
              <Select value={state} onChange={(event) => setState(event.target.value as typeof state)}>
                <option value="ready">{t("design.state.ready")}</option>
                <option value="loading">{t("design.state.loading")}</option>
                <option value="empty">{t("design.state.empty")}</option>
                <option value="error">{t("design.state.error")}</option>
              </Select>
            </Field>
          </div>
        </CardContent>
      </Card>
      <DataTable
        columns={columns}
        rows={state === "empty" ? [] : rows}
        rowKey={(row) => row.id}
        loading={state === "loading"}
        error={state === "error" ? t("design.error") : undefined}
        requestId={state === "error" ? "demo-request-1" : undefined}
        requestIdLabel={t("design.request_id")}
        onRetry={() => setState("ready")}
        retryLabel={t("design.retry")}
        emptyTitle={t("design.empty")}
        emptyDescription={t("design.empty.hint")}
        emptyAction={<Button onClick={() => setState("ready")}>{t("design.empty.action")}</Button>}
        toolbar={<span className="ui-help">{t("design.list.count", { count: rows.length })}</span>}
        caption={t("design.list.title")}
      />
    </div>
  );
}

function ReferenceForm() {
  const { t, locale } = useI18n();
  const [date, setDate] = useState("2026-09-11");
  return (
    <div className="ui-page">
      <PageHeader
        level={2}
        title={t("design.form.title")}
        description={t("design.form.description")}
      />
      <Card>
        <CardContent>
          <FormLayout onSubmit={(event) => event.preventDefault()}>
            <FormSection title={t("design.form.section.person")}>
              <FormGrid>
                <Field label={t("design.form.first")} required>
                  <Input defaultValue="Abebe" />
                </Field>
                <Field label={t("design.form.middle")}>
                  <Input defaultValue="Kebede" />
                </Field>
                <FormSpan>
                  <Field label={t("design.form.amharic")} hint={t("design.form.amharic.hint")}>
                    <Input className="amharic" defaultValue="አበበ ከበደ" />
                  </Field>
                </FormSpan>
              </FormGrid>
            </FormSection>
            <FormSection title={t("design.form.section.details")}>
              <FormGrid>
                <Field label={t("design.form.status")}>
                  <Select defaultValue="active">
                    <option value="active">{t("design.status.active")}</option>
                    <option value="pending">{t("design.status.pending")}</option>
                  </Select>
                </Field>
                <DatePicker
                  value={date}
                  onChange={setDate}
                  locale={locale}
                  label={t("design.form.date")}
                />
                <FormSpan>
                  <Field label={t("design.form.notes")}>
                    <Textarea placeholder={t("design.form.notes.hint")} />
                  </Field>
                </FormSpan>
              </FormGrid>
            </FormSection>
            <SaveBar>
              <Button variant="outline">{t("design.form.cancel")}</Button>
              <Button type="submit">{t("design.form.save")}</Button>
            </SaveBar>
          </FormLayout>
        </CardContent>
      </Card>
    </div>
  );
}

function ReferenceDashboard() {
  const { t, locale } = useI18n();
  const stats = [
    { key: "students", value: "1,248" },
    { key: "staff", value: "86" },
    { key: "attendance", value: "94%" },
    // Money always goes through the money layer, never a hand-built string.
    { key: "fees", value: formatSantim(128_450_000, { locale }) },
  ] as const;
  return (
    <div className="ui-page">
      <PageHeader
        level={2}
        title={t("design.dashboard.title")}
        description={t("design.dashboard.description")}
        actions={<Button variant="outline">{t("design.dashboard.export")}</Button>}
      />
      <div className="ui-form__grid">
        {stats.map((stat) => (
          <Card key={stat.key}>
            <CardHeader>
              <CardDescription>{t(`design.stat.${stat.key}`)}</CardDescription>
              <CardTitle>
                <span className="ui-num">{stat.value}</span>
              </CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t("design.dashboard.recent")}</CardTitle>
          <CardDescription>{t("design.dashboard.recent.hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {ROWS.length === 0 ? (
            <EmptyState title={t("design.empty")} />
          ) : (
            <ul className="ui-form__section">
              {ROWS.map((row) => (
                <li key={row.id} className="flex items-center justify-between gap-4 border-b border-border py-2">
                  <span>
                    <span className="font-medium">{row.name}</span>{" "}
                    <span className="amharic text-muted-foreground">{row.amharic}</span>
                  </span>
                  <span className="ui-help ui-num">{row.updated}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
