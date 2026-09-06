import { describe, expect, it } from "vitest";
import { isSystemProcessLocation } from "@/modules/services/isSystemProcessLocation";

describe("isSystemProcessLocation", () => {
  it("flags_backslash_system32_path_as_system_process", () => {
    expect(isSystemProcessLocation("C:\\Windows\\System32")).toBe(true);
  });

  it("flags_forward_slash_syswow64_path_as_system_process", () => {
    expect(isSystemProcessLocation("C:/Windows/SysWOW64/drivers")).toBe(true);
  });

  it("flags_windows_root_case_insensitively_as_system_process", () => {
    expect(isSystemProcessLocation("c:\\windows\\explorer")).toBe(true);
  });

  it("does_not_flag_a_project_directory_as_system_process", () => {
    expect(isSystemProcessLocation("C:/projects/fixture-web")).toBe(false);
  });

  it("does_not_flag_a_directory_that_merely_contains_windows_in_its_name", () => {
    expect(isSystemProcessLocation("C:\\Users\\bob\\Windows Projects\\app")).toBe(false);
  });

  it("does_not_flag_a_null_location", () => {
    expect(isSystemProcessLocation(null)).toBe(false);
  });
});
