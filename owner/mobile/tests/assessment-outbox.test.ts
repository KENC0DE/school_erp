import {
  discardMarks,
  flushOutbox,
  loadOutbox,
  queueMarks,
  saveOrQueue,
} from "../src/assessment/outbox";
import type { ScoreInput, ScoreSheet } from "../src/assessment/types";
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

function conflict(): SessionError {
  return new SessionError(
    "CONFLICT",
    "The mark changed since it was loaded",
    409,
  );
}

function sheet(assessmentId: string): ScoreSheet {
  return {
    assessment_id: assessmentId,
    title: "Quiz 1",
    component_key: "quizzes",
    component_max_points: "10",
    out_of: "15",
    allow_bonus: false,
    editable: true,
    items: [],
    stats: {
      total: 0,
      entered: 0,
      missing: 0,
      present: 0,
      absent: 0,
      excused: 0,
      exempt: 0,
      not_taken: 0,
      out_of: "15",
      component_max_points: "10",
      average_converted: null,
      average_percent: null,
      highest_converted: null,
      lowest_converted: null,
    },
  };
}

describe("mobile assessment outbox", () => {
  beforeEach(() => {
    mockCache.clear();
  });

  it("coalesces repeated edits of the same mark", async () => {
    await queueMarks("school-alpha", "exam-1", [
      {
        student_id: "student-1",
        raw_score: "10",
        status: "present",
        row_version: 1,
      },
    ]);
    await queueMarks("school-alpha", "exam-1", [
      {
        student_id: "student-1",
        raw_score: "12",
        status: "present",
        row_version: 1,
      },
      {
        student_id: "student-2",
        raw_score: null,
        status: "absent",
        row_version: null,
      },
    ]);

    const pending = await loadOutbox("school-alpha");
    expect(pending).toHaveLength(2);
    expect(
      pending.find((entry) => entry.student_id === "student-1"),
    ).toMatchObject({
      raw_score: "12",
      status: "present",
    });
  });

  it("queues a mark when the school cannot be reached", async () => {
    const result = await saveOrQueue(
      "school-alpha",
      "exam-1",
      {
        student_id: "student-1",
        raw_score: "9",
        status: "present",
        row_version: null,
      },
      async () => {
        throw networkError();
      },
    );

    expect(result).toEqual({ sheet: null, queued: 1, conflict: false });
    expect(await loadOutbox("school-alpha")).toHaveLength(1);
  });

  it("keeps a queued mark after a conflict so the teacher can choose", async () => {
    const result = await saveOrQueue(
      "school-alpha",
      "exam-1",
      {
        student_id: "student-1",
        raw_score: "11",
        status: "present",
        row_version: 1,
      },
      async () => {
        throw conflict();
      },
    );

    expect(result).toEqual({ sheet: null, queued: 1, conflict: true });
    expect(await loadOutbox("school-alpha")).toHaveLength(1);
  });

  it("replays offline marks once each and is idempotent", async () => {
    const server = new Map<string, { raw: string | null; status: string }>();
    let offline = true;
    const sent: ScoreInput[] = [];
    const send = async (
      _instanceId: string,
      assessmentId: string,
      item: ScoreInput,
    ): Promise<ScoreSheet> => {
      if (offline) throw networkError();
      sent.push(item);
      server.set(`${assessmentId}:${item.student_id}`, {
        raw: item.raw_score,
        status: item.status,
      });
      return sheet(assessmentId);
    };

    const items = [
      {
        student_id: "student-1",
        raw_score: "12",
        status: "present" as const,
        row_version: null,
      },
      {
        student_id: "student-2",
        raw_score: null,
        status: "absent" as const,
        row_version: null,
      },
      {
        student_id: "student-3",
        raw_score: "7",
        status: "present" as const,
        row_version: null,
      },
    ];
    for (const item of items) {
      await saveOrQueue("school-alpha", "exam-1", item, send);
    }
    expect(await loadOutbox("school-alpha")).toHaveLength(3);

    const stillOffline = await flushOutbox("school-alpha", send);
    expect(stillOffline).toMatchObject({ sent: 0, pending: 3, conflicts: [] });
    expect(server.size).toBe(0);

    offline = false;
    const replayed = await flushOutbox("school-alpha", send);
    expect(replayed).toMatchObject({ sent: 3, pending: 0, conflicts: [] });
    expect(server.size).toBe(3);
    expect(await loadOutbox("school-alpha")).toHaveLength(0);

    // A repeated sync sends nothing more, so no student can get a second score.
    const again = await flushOutbox("school-alpha", send);
    expect(again.sent).toBe(0);
    expect(sent).toHaveLength(3);
  });

  it("reports a stale mark as a conflict and resends it with a fresh version", async () => {
    const versions = new Map([["student-1", 1]]);
    const send = async (
      _instanceId: string,
      assessmentId: string,
      item: ScoreInput,
    ): Promise<ScoreSheet> => {
      if (versions.get(item.student_id) !== item.row_version) throw conflict();
      versions.set(item.student_id, (item.row_version ?? 0) + 1);
      return sheet(assessmentId);
    };

    await queueMarks("school-alpha", "exam-1", [
      {
        student_id: "student-1",
        raw_score: "13",
        status: "present",
        row_version: 1,
      },
    ]);
    versions.set("student-1", 2);

    const conflicted = await flushOutbox("school-alpha", send);
    expect(conflicted.sent).toBe(0);
    expect(conflicted.pending).toBe(1);
    expect(conflicted.conflicts).toHaveLength(1);

    // "Keep mine": requeue with the version the refreshed sheet returned.
    await queueMarks("school-alpha", "exam-1", [
      {
        student_id: "student-1",
        raw_score: "13",
        status: "present",
        row_version: 2,
      },
    ]);
    const resolved = await flushOutbox("school-alpha", send);
    expect(resolved).toMatchObject({ sent: 1, pending: 0, conflicts: [] });
    expect(await loadOutbox("school-alpha")).toHaveLength(0);
  });

  it("drops a queued mark when the server value wins", async () => {
    await queueMarks("school-alpha", "exam-1", [
      {
        student_id: "student-1",
        raw_score: "13",
        status: "present",
        row_version: 1,
      },
    ]);

    const remaining = await discardMarks("school-alpha", [
      { assessment_id: "exam-1", student_id: "student-1" },
    ]);
    expect(remaining).toHaveLength(0);
    expect(await loadOutbox("school-alpha")).toHaveLength(0);
  });
});
