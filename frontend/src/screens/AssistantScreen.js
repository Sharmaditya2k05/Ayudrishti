/**
 * Yoga Assistant -- retrieval-augmented Q&A over the asana library and a
 * curated yoga-knowledge base, answered by a Groq-hosted model on the
 * backend. Purely conversational; it never writes to the profile, plan or
 * session data, so there is nothing here to confirm before applying.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import api from '../api/client';
import DashboardHeader from '../components/DashboardHeader';
import MarkdownText from '../components/MarkdownText';
import { Card, ErrorNotice, Screen } from '../components/common';
import { colors, fonts, radius, spacing, typography } from '../theme/theme';

const SUGGESTIONS = [
  'What is pranayama?',
  'Is yoga safe during pregnancy?',
  'How often should a beginner practice?',
  'What are the eight limbs of yoga?',
];

export default function AssistantScreen({ navigation }) {
  const [status, setStatus] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.getAssistantStatus().then(setStatus).catch(() => setStatus({ configured: false }));
  }, []);

  const send = async (question) => {
    const text = (question ?? input).trim();
    if (!text || busy) return;
    setInput('');
    setError(null);
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setBusy(true);
    try {
      const result = await api.askAssistant(text);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: result.answer, sources: result.sources },
      ]);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd?.({ animated: true }));
    }
  };

  return (
    <Screen scroll={false}>
      <DashboardHeader navigation={navigation} />

      {status && !status.configured ? (
        <Card style={styles.warnCard}>
          <View style={styles.warnHeader}>
            <MaterialCommunityIcons name="robot-outline" size={18} color={colors.warn} />
            <Text style={typography.heading}>Assistant not configured</Text>
          </View>
          <Text style={[typography.bodyMuted, { marginTop: spacing.xs }]}>
            The yoga assistant needs a Groq API key on the backend (GROQ_API_KEY) before it
            can answer questions.
          </Text>
        </Card>
      ) : null}

      <ErrorNotice error={error} />

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1 }}
          contentContainerStyle={styles.messages}
          showsVerticalScrollIndicator={false}
        >
          {messages.length === 0 ? (
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <MaterialCommunityIcons name="robot-outline" size={30} color={colors.primary} />
              </View>
              <Text style={typography.heading}>Ask about yoga</Text>
              <Text style={[typography.bodyMuted, { marginTop: spacing.xs, textAlign: 'center' }]}>
                Poses, breathing, meditation, philosophy, safe practice -- grounded in
                AyuDrishti's own asana library and a curated knowledge base.
              </Text>
              <View style={styles.suggestions}>
                {SUGGESTIONS.map((s) => (
                  <Pressable key={s} style={styles.suggestion} onPress={() => send(s)}>
                    <Text style={styles.suggestionText}>{s}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : (
            messages.map((m, i) => <Message key={i} message={m} />)
          )}
          {busy ? (
            <View style={styles.typingRow}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.typingText}>Thinking...</Text>
            </View>
          ) : null}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ask a yoga question..."
            placeholderTextColor={colors.textFaint}
            onSubmitEditing={() => send()}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendButton, (!input.trim() || busy) && styles.sendButtonDisabled]}
            onPress={() => send()}
            disabled={!input.trim() || busy}
          >
            <MaterialCommunityIcons name="send" size={18} color={colors.bgDeep} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

function Message({ message }) {
  const isUser = message.role === 'user';
  return (
    <View style={[styles.bubbleRow, isUser && styles.bubbleRowUser]}>
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        {isUser ? (
          <Text style={[styles.bubbleText, styles.bubbleTextUser]}>{message.text}</Text>
        ) : (
          <MarkdownText text={message.text} style={styles.bubbleText} />
        )}
      </View>
      {!isUser && message.sources?.length ? (
        <View style={styles.sourcesRow}>
          <MaterialCommunityIcons name="book-open-outline" size={12} color={colors.textFaint} />
          <Text style={styles.sourcesText}>
            {message.sources.map((s) => s.title).join(' · ')}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  warnHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  warnCard: { borderColor: colors.warn, backgroundColor: colors.warnSoft },

  messages: { padding: spacing.md, paddingBottom: spacing.lg, flexGrow: 1 },

  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.xl },
  emptyIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primaryFaint,
    marginBottom: spacing.md,
  },
  suggestions: { marginTop: spacing.lg, gap: spacing.sm, width: '100%', maxWidth: 420 },
  suggestion: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSoft,
  },
  suggestionText: { fontFamily: fonts.body, fontSize: 13.5, color: colors.textMuted },

  bubbleRow: { marginBottom: spacing.md, alignItems: 'flex-start', maxWidth: '85%' },
  bubbleRowUser: { alignSelf: 'flex-end', alignItems: 'flex-end' },
  bubble: { borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  bubbleAssistant: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderTopLeftRadius: 4,
  },
  bubbleUser: { backgroundColor: colors.primary, borderTopRightRadius: 4 },
  bubbleText: { fontFamily: fonts.body, fontSize: 14.5, lineHeight: 21, color: colors.text },
  bubbleTextUser: { color: colors.bgDeep },
  sourcesRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4, paddingHorizontal: 2 },
  sourcesText: { fontFamily: fonts.body, fontSize: 10.5, color: colors.textFaint, flexShrink: 1 },

  typingRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.xs },
  typingText: { fontFamily: fonts.body, fontSize: 12.5, color: colors.textFaint },

  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgDeep,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    paddingHorizontal: spacing.md,
    paddingVertical: 11,
    fontSize: 14,
    fontFamily: fonts.body,
  },
  sendButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  sendButtonDisabled: { opacity: 0.4 },
});
