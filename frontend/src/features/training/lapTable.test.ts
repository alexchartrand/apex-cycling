import { describe, expect, it } from "vitest";
import { lapSpeedKmh, lapsToCsv, recordingColumns, splitColumns, splitMs } from "./lapTable";
import type { LapDetail, SegmentDetail } from "./types";

function seg(loopId: string, name: string, index: number, ms: number | null): SegmentDetail {
  return { sequence_index: index, loop_id: loopId, loop_name: name, time_ms: ms };
}

function lap(id: string, total: number | null, segments: SegmentDetail[], extra: Partial<LapDetail> = {}): LapDetail {
  return {
    lap_id: id,
    start_time: "2026-07-07T13:43:57.134Z",
    class_code: null,
    start_number: null,
    whole_lap_time_ms: total,
    excluded: false,
    label: null,
    segments,
    views: [],
    ...extra,
  };
}

const full = [seg("a", "Courbe 1", 0, 5000), seg("b", "200m", 1, 3000), seg("c", "Finish", 2, 17000)];

describe("splitColumns", () => {
  it("orders columns by checkpoint order and skips hidden checkpoints", () => {
    const columns = splitColumns([lap("1", 25000, full)], new Set(["a"]));
    expect(columns).toEqual([
      { loopId: "b", name: "200m" },
      { loopId: "c", name: "Finish" },
    ]);
  });

  it("lets the fullest lap set the order, then appends checkpoints only other laps have", () => {
    const partial = lap("1", null, [seg("a", "Courbe 1", 0, 5000), seg("x", "Extra", 1, 2000)]);
    const columns = splitColumns([partial, lap("2", 25000, full)], new Set());
    expect(columns.map((c) => c.loopId)).toEqual(["a", "b", "c", "x"]);
  });

  it("is empty with no laps", () => {
    expect(splitColumns([], new Set())).toEqual([]);
  });
});

describe("splitMs / lapSpeedKmh", () => {
  it("reads a split by checkpoint id, null when not captured", () => {
    const l = lap("1", 25000, [seg("a", "Courbe 1", 0, null), seg("b", "200m", 1, 3000)]);
    expect(splitMs(l, "b")).toBe(3000);
    expect(splitMs(l, "a")).toBeNull();
    expect(splitMs(l, "zzz")).toBeNull();
  });

  it("computes speed from the lap length", () => {
    expect(lapSpeedKmh(lap("1", 25000, []), 250)).toBeCloseTo(36);
    expect(lapSpeedKmh(lap("1", 25000, []), null)).toBeNull();
    expect(lapSpeedKmh(lap("1", null, []), 250)).toBeNull();
  });
});

describe("lapsToCsv", () => {
  it("writes a machine-readable table", () => {
    const columns = splitColumns([lap("1", 25000, full)], new Set(["a"]));
    const csv = lapsToCsv(
      [
        lap("1", 25000, full, { start_number: 1, label: "Opener" }),
        lap("2", null, [seg("b", "200m", 1, 3100)], { excluded: true, start_number: 2 }),
      ],
      columns,
      250,
    );
    expect(csv.split("\r\n")).toEqual([
      "lap,start_time,lap_time_s,speed_kmh,flying_200_s,200m_s,Finish_s,excluded,label",
      "1,2026-07-07T13:43:57.134Z,25.000,36.00,,3.000,17.000,no,Opener",
      "2,2026-07-07T13:43:57.134Z,,,,3.100,,yes,",
      "",
    ]);
  });

  it("quotes fields containing commas, quotes or newlines", () => {
    const csv = lapsToCsv([lap("1", 25000, [], { start_number: 1, label: 'Hard, "all out"\nthen easy' })], [], null);
    expect(csv).toContain('"Hard, ""all out""\nthen easy"');
  });

  it("falls back to the position when sqorz gave no start number", () => {
    const csv = lapsToCsv([lap("1", 25000, []), lap("2", 24000, [])], [], null);
    expect(csv.split("\r\n")[2].startsWith("2,")).toBe(true);
  });
});

describe("recorded channels in the lap table", () => {
  const recorded = (id: string, extra: Partial<LapDetail>) => lap(id, 25000, full, extra);

  it("knows which channels any lap has", () => {
    expect(recordingColumns([lap("1", 25000, full)])).toEqual({ power: false, heartRate: false, cadence: false });
    expect(recordingColumns([recorded("1", { avg_power_w: 300 }), recorded("2", { avg_cadence: 110 })])).toEqual({
      power: true,
      heartRate: false,
      cadence: true,
    });
  });

  it("adds power, heart rate and cadence to the CSV only when recorded", () => {
    const plain = lapsToCsv([lap("1", 25000, full)], [], 250).split("\r\n")[0];
    expect(plain).toBe("lap,start_time,lap_time_s,speed_kmh,flying_200_s,excluded,label");

    const csv = lapsToCsv([recorded("1", { avg_power_w: 612.4, avg_heart_rate: 171.6, avg_cadence: null })], [], 250).split("\r\n");
    expect(csv[0]).toBe("lap,start_time,lap_time_s,speed_kmh,flying_200_s,avg_power_w,avg_heart_rate_bpm,excluded,label");
    expect(csv[1]).toContain(",612,172,");
  });
});
