/**
 * Hands-free voice commands, via the browser's SpeechRecognition API.
 *
 * Only Chrome and Edge expose this (as `webkitSpeechRecognition`); Firefox
 * and Safari do not. `voiceCommandsSupported` lets a screen hide voice-only
 * UI rather than break there -- every caller must keep its buttons as the
 * primary path and treat voice purely as a hands-free bonus layered on top.
 */

import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

function getRecognitionCtor() {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export const voiceCommandsSupported = Boolean(getRecognitionCtor());

/**
 * @param {boolean} enabled - whether to actively listen right now
 * @param {string} [lang] - BCP-47 recognition language, e.g. 'en-US' or 'hi-IN'
 * @param {Record<string, string[]>} commands - command name -> accepted phrases
 * @param {(command: string) => void} onCommand
 */
export function useVoiceCommands({ enabled, lang = 'en-US', commands, onCommand }) {
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState(null);

  // Refs so the effect below doesn't need `commands`/`onCommand` in its
  // dependency array -- those are typically new object/function literals
  // every render, which would otherwise tear down and restart recognition
  // (and the browser permission prompt with it) on every keystroke-sized change.
  const onCommandRef = useRef(onCommand);
  const commandsRef = useRef(commands);
  onCommandRef.current = onCommand;
  commandsRef.current = commands;

  useEffect(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor || !enabled) {
      setListening(false);
      return undefined;
    }

    let fatal = false;
    setMicError(null);

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = lang;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((r) => r[0]?.transcript ?? '')
        .join(' ')
        .toLowerCase();
      for (const [command, phrases] of Object.entries(commandsRef.current ?? {})) {
        if (phrases.some((p) => transcript.includes(p.toLowerCase()))) {
          onCommandRef.current?.(command);
          break;
        }
      }
    };

    recognition.onerror = (event) => {
      // 'no-speech' fires constantly during ordinary silence -- not an
      // error worth surfacing or stopping for. Permission/device issues are.
      if (event.error === 'not-allowed' || event.error === 'audio-capture') {
        fatal = true;
        setMicError(event.error);
        setListening(false);
      }
    };

    recognition.onend = () => {
      // Browsers end a recognition session after a pause even in
      // `continuous` mode; restart it for as long as this screen still
      // wants to be listening.
      if (!fatal) {
        try {
          recognition.start();
        } catch {
          /* already starting/started -- ignore */
        }
      } else {
        setListening(false);
      }
    };

    try {
      recognition.start();
      setListening(true);
    } catch (err) {
      setMicError(err?.message ?? 'Could not start voice recognition.');
    }

    return () => {
      fatal = true; // stop the auto-restart in onend during teardown
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.stop();
      setListening(false);
    };
  }, [enabled, lang]);

  return { supported: Boolean(getRecognitionCtor()), listening, micError };
}
