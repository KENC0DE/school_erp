import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  Badge,
  Button,
  DataTable,
  DatePicker,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Tabs,
  ToastProvider,
  useToast,
} from "../src";

describe("shared web UI kit", () => {
  it("renders buttons with variants and a loading state", () => {
    render(
      <>
        <Button variant="secondary">Save</Button>
        <Button loading>Working</Button>
      </>,
    );
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toHaveClass("ui-btn", "ui-btn--secondary");
    expect(screen.getByRole("button", { name: "Working" })).toBeDisabled();
  });

  it("links a label to its input and shows an error instead of a hint", () => {
    render(
      <Field label="School code" hint="Three letters" error="Required">
        <Input aria-label="code" />
      </Field>,
    );
    expect(screen.getByText("School code")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
    expect(screen.queryByText("Three letters")).not.toBeInTheDocument();
  });

  it("renders status badges with a semantic variant", () => {
    render(<Badge variant="success">Active</Badge>);
    expect(screen.getByText("Active")).toHaveClass("ui-badge--success");
  });

  it("shows loading, empty and error states in the data table", () => {
    const columns = [{ key: "name", header: "Name", render: (row: { id: string; name: string }) => row.name }];
    const { rerender } = render(
      <DataTable columns={columns} rows={[]} rowKey={(row) => row.id} loading />,
    );
    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();
    expect(document.querySelectorAll(".ui-skeleton").length).toBeGreaterThan(0);
    rerender(<DataTable columns={columns} rows={[]} rowKey={(row) => row.id} emptyTitle="No students" />);
    expect(screen.getByText("No students")).toBeInTheDocument();
    rerender(
      <DataTable columns={columns} rows={[]} rowKey={(row) => row.id} error="Could not load" requestId="req-1" />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
    expect(screen.getByText("req-1")).toBeInTheDocument();
  });

  it("renders rows and stacks cell labels for phones", () => {
    render(
      <DataTable
        columns={[{ key: "name", header: "Name", render: (row: { id: string; name: string }) => row.name }]}
        rows={[{ id: "1", name: "Abebe" }]}
        rowKey={(row) => row.id}
      />,
    );
    expect(screen.getByRole("cell", { name: "Abebe" })).toHaveAttribute("data-label", "Name");
  });

  it("opens a dialog, closes on Escape and restores focus", () => {
    const onClose = vi.fn();
    render(
      <>
        <button type="button">Open</button>
        <Dialog open onClose={onClose} title="Delete student">
          Body
        </Dialog>
      </>,
    );
    expect(screen.getByRole("dialog", { name: "Delete student" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("switches tabs with the keyboard", () => {
    render(
      <Tabs
        items={[
          { key: "a", label: "First", content: <p>Panel A</p> },
          { key: "b", label: "Second", content: <p>Panel B</p> },
        ]}
      />,
    );
    expect(screen.getByText("Panel A")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("tab", { name: "First" }), { key: "ArrowRight" });
    expect(screen.getByText("Panel B")).toBeInTheDocument();
  });

  it("shows the Ethiopian and Gregorian representations", () => {
    render(<DatePicker value="2026-09-11" onChange={() => {}} preference="both" label="Date" />);
    expect(screen.getByLabelText("Date")).toHaveValue("2026-09-11");
    expect(screen.getByTestId("date-picker-display")).toHaveTextContent("Meskerem");
    expect(screen.getByTestId("date-picker-display")).toHaveTextContent("2026");
  });

  it("announces an empty state with a next action", () => {
    render(<EmptyState title="No notes" description="Add the first note" action={<Button>Add note</Button>} />);
    expect(screen.getByRole("status")).toHaveTextContent("No notes");
    expect(screen.getByRole("button", { name: "Add note" })).toBeInTheDocument();
  });

  it("renders an error state with the request id", () => {
    render(<ErrorState title="Request failed" requestId="abc" retry={<Button>Retry</Button>} />);
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("abc")).toBeInTheDocument();
  });

  it("pushes a toast through the provider", async () => {
    function Trigger() {
      const toast = useToast();
      return (
        <Button onClick={() => toast.push({ title: "Saved", variant: "success" })}>Save</Button>
      );
    }
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });
});
