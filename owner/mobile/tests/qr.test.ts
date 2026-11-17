import { normaliseSchoolCode, parseSchoolQrPayload } from "../src/directory/qr";

describe("QR payload parser", () => {
  it("parses erpapp://school/<code> and normalises the code", () => {
    expect(parseSchoolQrPayload("erpapp://school/demo")).toBe("DEMO");
    expect(parseSchoolQrPayload("  ERPAPP://SCHOOL/DEMO2/  ")).toBe("DEMO2");
    expect(parseSchoolQrPayload("erpapp://school/A1B2C3")).toBe("A1B2C3");
  });

  it("rejects other URLs, empty values and invalid codes", () => {
    expect(parseSchoolQrPayload("https://school.example/DEMO")).toBeNull();
    expect(parseSchoolQrPayload("erpapp://school/")).toBeNull();
    expect(parseSchoolQrPayload("erpapp://class/DEMO")).toBeNull();
    expect(parseSchoolQrPayload("erpapp://school/D")).toBeNull();
    expect(parseSchoolQrPayload("erpapp://school/DEMO/extra")).toBeNull();
    expect(parseSchoolQrPayload("")).toBeNull();
  });

  it("normalises a manually typed school code", () => {
    expect(normaliseSchoolCode(" demo ")).toBe("DEMO");
    expect(normaliseSchoolCode("demo-2")).toBe("DEMO-2");
    expect(normaliseSchoolCode("not a code")).toBeNull();
  });
});
