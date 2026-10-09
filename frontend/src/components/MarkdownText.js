/**
 * Minimal Markdown renderer for assistant answers.
 *
 * Deliberately tiny and dependency-free: the assistant emits a constrained
 * subset of Markdown (paragraphs, `###` headings, `-`/`1.` lists, `**bold**`
 * and `[label](url)` links), and this renders exactly that with React Native
 * primitives so it works identically on web and native. It is not a general
 * Markdown engine -- anything it doesn't recognise falls through as plain text.
 */

import React from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '../theme/theme';

const INLINE = /(\*\*([^*]+)\*\*)|(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))/g;

// Turn a single line of text into an array of <Text> spans, handling **bold**
// and [label](url). Links are tappable and open in the browser / device.
function renderInline(text, baseStyle, keyPrefix) {
  const nodes = [];
  let lastIndex = 0;
  let match;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(
        <Text key={`${keyPrefix}-t${i}`} style={baseStyle}>
          {text.slice(lastIndex, match.index)}
        </Text>,
      );
      i += 1;
    }
    if (match[1]) {
      nodes.push(
        <Text key={`${keyPrefix}-b${i}`} style={[baseStyle, styles.bold]}>
          {match[2]}
        </Text>,
      );
    } else if (match[3]) {
      const label = match[4];
      const url = match[5];
      nodes.push(
        <Text
          key={`${keyPrefix}-l${i}`}
          style={[baseStyle, styles.link]}
          onPress={() => Linking.openURL(url).catch(() => {})}
        >
          {label}
        </Text>,
      );
    }
    i += 1;
    lastIndex = INLINE.lastIndex;
  }
  if (lastIndex < text.length) {
    nodes.push(
      <Text key={`${keyPrefix}-t${i}`} style={baseStyle}>
        {text.slice(lastIndex)}
      </Text>,
    );
  }
  return nodes;
}

export default function MarkdownText({ text, style }) {
  const base = style;
  const lines = String(text ?? '').replace(/\r\n/g, '\n').split('\n');

  const blocks = [];
  let list = null;
  const flushList = () => {
    if (list) {
      blocks.push({ type: 'list', ordered: list.ordered, items: list.items });
      list = null;
    }
  };

  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) {
      flushList();
      return;
    }
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    const bullet = line.match(/^[-*]\s+(.*)$/);
    const ordered = line.match(/^\d+\.\s+(.*)$/);

    if (heading) {
      flushList();
      blocks.push({ type: 'heading', text: heading[1] });
    } else if (bullet) {
      if (!list || list.ordered) {
        flushList();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
    } else if (ordered) {
      if (!list || !list.ordered) {
        flushList();
        list = { ordered: true, items: [] };
      }
      list.items.push(ordered[1]);
    } else {
      flushList();
      blocks.push({ type: 'p', text: line });
    }
  });
  flushList();

  return (
    <View>
      {blocks.map((block, i) => {
        if (block.type === 'heading') {
          const hStyle = [base, styles.heading];
          return (
            <Text key={i} style={hStyle}>
              {renderInline(block.text, hStyle, `h${i}`)}
            </Text>
          );
        }
        if (block.type === 'p') {
          return (
            <Text key={i} style={[base, i > 0 && styles.paraGap]}>
              {renderInline(block.text, base, `p${i}`)}
            </Text>
          );
        }
        return (
          <View key={i} style={[styles.list, i > 0 && styles.paraGap]}>
            {block.items.map((item, j) => (
              <View key={j} style={styles.listItem}>
                <Text style={[base, styles.marker]}>
                  {block.ordered ? `${j + 1}.` : '•'}
                </Text>
                <Text style={[base, styles.listText]}>
                  {renderInline(item, base, `l${i}-${j}`)}
                </Text>
              </View>
            ))}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bold: { fontFamily: fonts.bodyBold ?? fonts.body, fontWeight: '700' },
  link: { color: colors.primary, textDecorationLine: 'underline' },
  heading: { fontFamily: fonts.bodyBold ?? fonts.body, fontWeight: '700', marginBottom: 2 },
  paraGap: { marginTop: 8 },
  list: { gap: 4 },
  listItem: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
  marker: { opacity: 0.7 },
  listText: { flex: 1 },
});
