import { fireEvent, render } from "@testing-library/react-native";

import { EMPTY_NAME, NameFields } from "../src/components/NameFields";
import { defaultNativeTheme } from "../src/theme/nativeTheme";

const colors = defaultNativeTheme("light").colors;

describe("NameFields (mobile)", () => {
  it("renders three fields for each script and explains that there is no last name", async () => {
    const view = await render(
      <NameFields colors={colors} locale="en" value={EMPTY_NAME} onChange={() => {}} />,
    );
    for (const field of [
      "given_name_en",
      "father_name_en",
      "grandfather_name_en",
      "given_name_am",
      "father_name_am",
      "grandfather_name_am",
    ]) {
      expect(view.getByTestId(`name-${field}`)).toBeTruthy();
    }
    expect(view.getByText(/no last name/i)).toBeTruthy();
  });

  it("edits the Amharic fields without touching the Latin ones", async () => {
    const onChange = jest.fn();
    const view = await render(
      <NameFields colors={colors} locale="en" value={EMPTY_NAME} onChange={onChange} />,
    );
    fireEvent.changeText(view.getByTestId("name-given_name_am"), "አበበ");
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_NAME, given_name_am: "አበበ" });
  });

  it("shows Amharic labels in the Amharic locale", async () => {
    const view = await render(
      <NameFields colors={colors} locale="am" value={EMPTY_NAME} onChange={() => {}} />,
    );
    expect(view.getAllByText("የራስ ስም").length).toBeGreaterThan(0);
  });
});
