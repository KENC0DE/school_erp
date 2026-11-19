import {
  flushOutbox,
  loadOutbox,
  queueRecords,
  saveOrQueue,
} from "../src/attendance/outbox";
import type { RecordInput, SessionDetail } from "../src/attendance/types";
import { SessionError } from "../src/session/session";

const mockCache = new Map<string, unknown>();

jest.mock("../src/storage/schoolStorage", () => ({
  forSchool: () => ({
    getCache: async (name: string) => mockCache.get(name) ?? null,
    setCache: async (name: string, value: unknown) => {
      mockCache.set(name, value);
    },
  }),
}));

function networkError(): SessionError {
  return new SessionError("NETWORK_ERROR", "Cannot reach the school server");
}

describe("attendance offline outbox", () => {
  beforeEach(() => {
    mockCache.clear();
  });

  it("coalesces repeated offline edits by session and student", async () => {
    await queueRecords("school-alpha", "session-1", [
      { student_id: "student-1", status: "absent", reason: "Sick" },
    ]);
    await queueRecords("school-alpha", "session-1", [
      { student_id: "student-1", status: "excused", reason: "Medical" },
      { student_id: "student-2", status: "late", late_minutes: 10 },
    ]);

    const pending = await loadOutbox("school-alpha");
    expect(pending).toHaveLength(2);
    expect(pending.find((entry) => entry.student_id === "student-1")).toMatchObject({
      status: "excused",
      reason: "Medical",
    });
  });

  it("queues entries when the save fails offline", async () => {
    const result = await saveOrQueue(
      "school-alpha",
      "session-1",
      [{ student_id: "student-1", status: "absent" }],
      async () => {
        throw networkError();
      },
    );

    expect(result.detail).toBeNull();
    expect(result.queued).toBe(1);
    expect(await loadOutbox("school-alpha")).toHaveLength(1);
  });

  it("replays after reconnecting and keeps exactly one record per student", async () => {
    const server = new Map<string, { student_id: string; status: string }>();
    let offline = true;
    let saves = 0;
    const send = async (
      _instanceId: string,
      _sessionId: string,
      items: RecordInput[],
    ): Promise<SessionDetail> => {
      saves += 1;
      if (offline) throw networkError();
      for (const item of items) {
        server.set(item.student_id, { student_id: item.student_id, status: item.status });
      }
      return { id: "session-1", records: [], roster: [] } as unknown as SessionDetail;
    };

    const entries: RecordInput[] = [
      { student_id: "student-1", status: "absent" },
      { student_id: "student-2", status: "late", late_minutes: 5 },
      { student_id: "student-3", status: "present" },
    ];
    const first = await saveOrQueue("school-alpha", "session-1", entries, send);
    expect(first.queued).toBe(3);

    const stillOffline = await flushOutbox("school-alpha", send);
    expect(stillOffline).toMatchObject({ sent: 0, pending: 3 });
    expect(server.size).toBe(0);

    offline = false;
    const replayed = await flushOutbox("school-alpha", send);
    expect(replayed).toMatchObject({ sent: 3, pending: 0 });
    expect(server.size).toBe(3);

    // Replaying a stale request must not create duplicate rows for a student.
    await send("school-alpha", "session-1", entries);
    expect(server.size).toBe(3);
    expect(saves).toBe(4);
    expect(await loadOutbox("school-alpha")).toHaveLength(0);
  });
});
