import type { Tone } from "../ui";
import type { StaffStatus } from "./types";

/** Status colors stay semantic and come from the shared palette tones. */
export function statusTone(status: StaffStatus): Tone {
  if (status === "active") return "success";
  if (status === "on_leave") return "warning";
  if (status === "terminated") return "danger";
  return "neutral";
}
