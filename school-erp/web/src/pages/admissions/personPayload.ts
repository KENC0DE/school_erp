import type { NameValue } from "../../components/NameFields";
import type { ApplicantDraft } from "./ApplicantFields";

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

/** Translate the visible draft into the `PersonInput` the API expects. */
export function personPayload(draft: ApplicantDraft): Record<string, string | null> {
  const names: NameValue = draft.names;
  return {
    given_name_en: clean(names.given_name_en),
    father_name_en: clean(names.father_name_en),
    grandfather_name_en: clean(names.grandfather_name_en),
    given_name_am: clean(names.given_name_am),
    father_name_am: clean(names.father_name_am),
    grandfather_name_am: clean(names.grandfather_name_am),
    sex: draft.sex || null,
    date_of_birth: draft.dateOfBirth || null,
    place_of_birth: clean(draft.placeOfBirth),
    nationality: clean(draft.nationality),
    phone: clean(draft.phone),
    email: clean(draft.email),
    address: clean(draft.address),
  };
}

export function draftFromPerson(person: {
  given_name_en: string | null;
  father_name_en: string | null;
  grandfather_name_en: string | null;
  given_name_am: string | null;
  father_name_am: string | null;
  grandfather_name_am: string | null;
  sex: string | null;
  date_of_birth: string | null;
  place_of_birth: string | null;
  nationality: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
}): ApplicantDraft {
  return {
    names: {
      given_name_en: person.given_name_en ?? "",
      father_name_en: person.father_name_en ?? "",
      grandfather_name_en: person.grandfather_name_en ?? "",
      given_name_am: person.given_name_am ?? "",
      father_name_am: person.father_name_am ?? "",
      grandfather_name_am: person.grandfather_name_am ?? "",
    },
    sex: person.sex ?? "",
    dateOfBirth: person.date_of_birth ?? "",
    placeOfBirth: person.place_of_birth ?? "",
    nationality: person.nationality ?? "",
    phone: person.phone ?? "",
    email: person.email ?? "",
    address: person.address ?? "",
  };
}
