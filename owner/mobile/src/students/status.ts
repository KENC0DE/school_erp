import type { Tone } from "../ui";
import type { StudentStatus } from "./types";

/** Status colors stay semantic and come from the shared palette tones. */
export function statusTone(status: StudentStatus): Tone {
  if (status === "active") return "success";
  if (status === "promoted" || status === "repeating") return "warning";
  if (status === "transferred_out" || status === "withdrawn") return "danger";
  return "neutral";
}
