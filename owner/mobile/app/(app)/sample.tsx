import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { useApp } from "../../src/context/AppContext";
import { useSchoolI18n } from "../../src/i18n/SchoolI18nContext";
import { authorizedJson, SessionError } from "../../src/session/session";
import { useSchoolThemeContext } from "../../src/theme/SchoolThemeContext";
import { Button, Card, Field, Title } from "../../src/ui/primitives";

interface Note {
  id: string;
  content: string;
  author_name: string;
  created_at: string | null;
}

interface NoteList {
  items: Note[];
}

function errorMessageKey(code: string | undefined): string {
  if (code === "MODULE_DISABLED") return "error.module_disabled";
  if (code === "PERMISSION_DENIED") return "error.permission_denied";
  return "common.error";
}

export default function SampleScreen() {
  const { profile, locale } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;
  const [notes, setNotes] = useState<Note[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorCode, setErrorCode] = useState<string | undefined>(undefined);

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    setErrorCode(undefined);
    try {
      const data = await authorizedJson<NoteList>(profile.instanceId, "/api/v1/sample/notes");
      setNotes(data.items);
    } catch (caught) {
      setErrorCode(caught instanceof SessionError ? caught.code : "HTTP_ERROR");
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addNote(): Promise<void> {
    if (!profile || content.trim() === "") return;
    setSaving(true);
    setErrorCode(undefined);
    try {
      const note = await authorizedJson<Note>(profile.instanceId, "/api/v1/sample/notes", {
        method: "POST",
        body: { content: content.trim() },
      });
      setNotes((current) => [note, ...current]);
      setContent("");
    } catch (caught) {
      setErrorCode(caught instanceof SessionError ? caught.code : "HTTP_ERROR");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Title colors={colors}>{t("sample.title")}</Title>
      <Text style={[styles.body, { color: colors.mutedForeground }]}>{t("sample.intro")}</Text>

      <Card colors={colors} style={styles.card}>
        <Text style={[styles.section, { color: colors.foreground }]}>{t("sample.notes")}</Text>
        {loading ? (
          <ActivityIndicator color={colors.primary} />
        ) : notes.length === 0 ? (
          <Text style={[styles.body, { color: colors.mutedForeground }]}>{t("sample.empty")}</Text>
        ) : (
          notes.map((note) => (
            <View key={note.id} style={[styles.note, { borderBottomColor: colors.border }]}>
              <Text style={{ color: colors.foreground, fontSize: 15 }}>{note.content}</Text>
              <Text style={[styles.meta, { color: colors.mutedForeground }]}>
                {note.author_name}
                {note.created_at
                  ? ` · ${new Date(note.created_at).toLocaleString(locale === "am" ? "am-ET" : "en-GB")}`
                  : ""}
              </Text>
            </View>
          ))
        )}
      </Card>

      {errorCode ? (
        <Text style={[styles.error, { color: colors.destructive }]}>{t(errorMessageKey(errorCode))}</Text>
      ) : null}

      <Card colors={colors} style={styles.card}>
        <Field
          colors={colors}
          label={t("sample.add_note")}
          placeholder={t("sample.note_placeholder")}
          value={content}
          onChangeText={setContent}
          multiline
          style={styles.noteInput}
        />
        <Button
          colors={colors}
          label={t("sample.add_note")}
          busy={saving}
          disabled={content.trim() === ""}
          onPress={() => void addNote()}
        />
      </Card>

      <View style={styles.retry}>
        <Button colors={colors} secondary label={t("common.retry")} onPress={() => void load()} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 40, gap: 12 },
  body: { fontSize: 15, lineHeight: 22 },
  section: { fontSize: 16, fontWeight: "700", marginBottom: 10 },
  card: { gap: 10 },
  note: { paddingVertical: 10, borderBottomWidth: 1, gap: 4 },
  meta: { fontSize: 12 },
  error: { fontSize: 14 },
  noteInput: { minHeight: 80, textAlignVertical: "top" },
  retry: { marginTop: 4 },
});
