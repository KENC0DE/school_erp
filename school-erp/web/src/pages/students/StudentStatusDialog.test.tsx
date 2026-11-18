import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../../providers/I18nProvider";
import { StudentStatusDialog } from "./StudentStatusDialog";
import type { StudentDetail } from "./types";

const messages: Record<string, string> = {
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.request_id": "Request id",
  "students.status.active": "Active",
  "students.status.graduated": "Graduated",
  "students.progress.change_status": "Change status",
  "students.progress.status.title": "Change student status",
  "students.progress.status.action": "Action",
  "students.progress.status.exit_date": "Exit date",
  "students.progress.status.exit_reason": "Reason",
  "students.progress.status.reason_hint": "Shown in the student record.",
  "students.progress.status.submit": "Save status",
  "students.progress.status.saving": "Saving…",
  "students.progress.status.failed": "The status could not be changed.",
  "students.progress.status.current": "Current status: {{status}}",
  "students.progress.status.action.transfer_out": "Transfer out",
  "students.progress.status.action.withdraw": "Withdraw",
  "students.progress.status.action.graduate": "Graduate",
  "students.progress.status.action.alumni": "Convert to alumni",
  "students.progress.status.action.reinstate": "Reinstate",
};

const STUDENT = {
  id: "student-1",
  student_number: "S-0001",
  status: "active",
  admission_date: "2026-09-15",
  row_version: 3,
  person: { full_name: "Abebe Kebede Tessema" },
  enrollment: null,
  exit_date: null,
  exit_reason: null,
  notes: null,
  custom: {},
  enrollments: [],
  guardians: [],
  medical: null,
} as unknown as StudentDetail;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let requests: {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}[] = [];

function renderDialog(student: StudentDetail = STUDENT, onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <I18nProvider initialMessages={messages}>
        <StudentStatusDialog student={student} open onClose={onClose} />
      </I18nProvider>
    </QueryClientProvider>,
  );
  return onClose;
}

beforeEach(() => {
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const request = {
        url,
        method: (init?.method ?? "GET").toUpperCase(),
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      requests.push(request);
      if (
        request.method === "POST" &&
        url.endsWith("/api/v1/students/student-1/status")
      ) {
        return json({
          action: "withdraw",
          changed: true,
          student: {
            ...STUDENT,
            status: "withdrawn",
            exit_reason: "Family moved",
          },
        });
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("student status dialog", () => {
  it("requires a reason for a withdrawal and posts the transition", async () => {
    const onClose = renderDialog();

    expect(screen.getByText("Current status: Active")).toBeInTheDocument();
    const action = screen.getByTestId("student-status-action");
    expect(action).toHaveValue("transfer_out");

    fireEvent.change(action, { target: { value: "withdraw" } });
    const submit = screen.getByRole("button", { name: "Save status" });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByTestId("student-status-exit-reason"), {
      target: { value: "Family moved" },
    });
    expect(submit).not.toBeDisabled();
    fireEvent.click(submit);

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(requests[0].body).toMatchObject({
      action: "withdraw",
      exit_reason: "Family moved",
      row_version: 3,
    });
  });

  it("only offers alumni conversion once a student has graduated", () => {
    renderDialog({ ...STUDENT, status: "graduated" });
    const options = Array.from(
      (screen.getByTestId("student-status-action") as HTMLSelectElement)
        .options,
    ).map((option) => option.value);
    expect(options).toEqual(["alumni"]);
  });
});
