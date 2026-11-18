import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, Field, Input, Select, Textarea } from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { CalendarDatePicker } from "../../components/CalendarDatePicker";
import { NameFields, type NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useDepartments, usePositions } from "./queries";
import { STAFF_STATUSES, type StaffDetail, type StaffStatus } from "./types";

function namesOf(staff: StaffDetail | null): NameValue {
  return {
    given_name_en: staff?.person.given_name_en ?? "",
    father_name_en: staff?.person.father_name_en ?? "",
    grandfather_name_en: staff?.person.grandfather_name_en ?? "",
    given_name_am: staff?.person.given_name_am ?? "",
    father_name_am: staff?.person.father_name_am ?? "",
    grandfather_name_am: staff?.person.grandfather_name_am ?? "",
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function StaffFormDialog({
  open,
  staff,
  onClose,
  onSaved,
}: {
  open: boolean;
  staff?: StaffDetail | null;
  onClose: () => void;
  onSaved?: (staff: StaffDetail) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const editing = Boolean(staff);
  const departments = useDepartments();
  const [names, setNames] = useState<NameValue>(() => namesOf(staff ?? null));
  const [sex, setSex] = useState(staff?.person.sex ?? "");
  const [dob, setDob] = useState(staff?.person.date_of_birth ?? "");
  const [phone, setPhone] = useState(staff?.person.phone ?? "");
  const [email, setEmail] = useState(staff?.person.email ?? "");
  const [address, setAddress] = useState(staff?.person.address ?? "");
  const [staffNumber, setStaffNumber] = useState(staff?.staff_number ?? "");
  const [status, setStatus] = useState<StaffStatus>(staff?.status ?? "active");
  const [departmentId, setDepartmentId] = useState(staff?.department?.id ?? "");
  const [positionId, setPositionId] = useState(staff?.position?.id ?? "");
  const [hireDate, setHireDate] = useState(staff?.hire_date ?? "");
  const [endDate, setEndDate] = useState(staff?.end_date ?? "");
  const [notes, setNotes] = useState(staff?.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  const positions = usePositions(departmentId);

  const save = useMutation({
    mutationFn: () => {
      const person = {
        ...Object.fromEntries(
          Object.entries(names).map(([key, value]) => [key, clean(value)]),
        ),
        sex: clean(sex),
        date_of_birth: clean(dob),
        phone: clean(phone),
        email: clean(email),
        address: clean(address),
      };
      if (staff) {
        return api.patch<StaffDetail>(`${STAFF}/${staff.id}`, {
          person,
          staff_number: clean(staffNumber),
          status,
          department_id: departmentId || null,
          position_id: positionId || null,
          hire_date: clean(hireDate),
          end_date: clean(endDate),
          notes: clean(notes),
          row_version: staff.row_version,
        });
      }
      return api.post<StaffDetail>(STAFF, {
        person,
        ...(clean(staffNumber) ? { staff_number: clean(staffNumber) } : {}),
        status,
        department_id: departmentId || null,
        position_id: positionId || null,
        hire_date: clean(hireDate),
        end_date: clean(endDate),
        notes: clean(notes),
      });
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "detail", saved.id] });
      onSaved?.(saved);
      onClose();
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError
          ? caught.message
          : t(editing ? "staff.edit.failed" : "staff.create.failed"),
      );
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      title={t(editing ? "staff.edit.title" : "staff.create.title")}
      description={t("staff.intro")}
      closeLabel={t("common.close")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form="staff-form" disabled={save.isPending}>
            {save.isPending
              ? t(editing ? "staff.edit.saving" : "staff.create.saving")
              : t("common.save")}
          </Button>
        </>
      }
    >
      <form id="staff-form" className="space-y-4" onSubmit={submit}>
        <NameFields value={names} onChange={setNames} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("staff.person.sex")}>
            <Select value={sex} onChange={(event) => setSex(event.target.value)}>
              <option value="">{t("staff.person.sex.unspecified")}</option>
              <option value="male">{t("staff.person.sex.male")}</option>
              <option value="female">{t("staff.person.sex.female")}</option>
            </Select>
          </Field>
          <Field label={t("staff.person.date_of_birth")}>
            <Input
              type="date"
              value={dob}
              onChange={(event) => setDob(event.target.value)}
            />
          </Field>
          <Field label={t("staff.person.phone")}>
            <Input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </Field>
          <Field label={t("staff.person.email")}>
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("staff.person.address")}>
              <Input value={address} onChange={(event) => setAddress(event.target.value)} />
            </Field>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("staff.staff_number")}>
            <Input
              data-testid="staff-number-input"
              required={editing}
              value={staffNumber}
              onChange={(event) => setStaffNumber(event.target.value)}
              placeholder={t("staff.create.number_hint")}
            />
          </Field>
          <Field label={t("staff.status")}>
            <Select
              value={status}
              onChange={(event) => setStatus(event.target.value as StaffStatus)}
            >
              {STAFF_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {t(`staff.status.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("staff.department")}>
            <Select
              value={departmentId}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPositionId("");
              }}
            >
              <option value="">{t("staff.filter.all_departments")}</option>
              {(departments.data?.items ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("staff.position")}>
            <Select
              value={positionId}
              onChange={(event) => setPositionId(event.target.value)}
            >
              <option value="">{t("staff.filter.all_positions")}</option>
              {(positions.data?.items ?? []).map((position) => (
                <option key={position.id} value={position.id}>
                  {position.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("staff.hire_date")}>
            <CalendarDatePicker value={hireDate} onChange={setHireDate} />
          </Field>
          <Field label={t("staff.end_date")}>
            <CalendarDatePicker value={endDate} onChange={setEndDate} />
          </Field>
          <div className="sm:col-span-2">
            <Field label={t("staff.notes")}>
              <Textarea
                value={notes}
                rows={3}
                onChange={(event) => setNotes(event.target.value)}
              />
            </Field>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          {t("staff.create.number_hint")}
        </p>

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
