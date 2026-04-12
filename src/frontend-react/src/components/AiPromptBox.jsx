import React, { useState, useRef, useEffect, useCallback, createContext, useContext, forwardRef } from 'react';
import { ArrowUp, Square, Mic, StopCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const cn = (...classes) => classes.filter(Boolean).join(' ');

// ── Textarea ─────────────────────────────────────────────────────────────────
const Textarea = forwardRef(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      'flex w-full rounded-md border-none bg-transparent px-3 py-2.5 text-base text-gray-100 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] resize-none',
      className
    )}
    ref={ref}
    rows={1}
    {...props}
  />
));
Textarea.displayName = 'Textarea';

// ── PromptInput context ───────────────────────────────────────────────────────
const PromptInputContext = createContext({
  isLoading: false,
  value: '',
  setValue: () => {},
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
});
const usePromptInput = () => useContext(PromptInputContext);

// ── PromptInput (outer container) ─────────────────────────────────────────────
const PromptInput = forwardRef(
  ({ className, isLoading = false, maxHeight = 240, value, onValueChange, onSubmit, children, disabled = false }, ref) => {
    const [internalValue, setInternalValue] = useState(value || '');
    const handleChange = (newValue) => {
      setInternalValue(newValue);
      onValueChange?.(newValue);
    };
    return (
      <PromptInputContext.Provider value={{ isLoading, value: value ?? internalValue, setValue: onValueChange ?? handleChange, maxHeight, onSubmit, disabled }}>
        <div
          ref={ref}
          className={cn(
            'rounded-3xl border border-[#3a3a3a] bg-[#141414] p-2 shadow-[0_8px_30px_rgba(0,0,0,0.4)] transition-all duration-300',
            isLoading && 'border-[#F59E0B]/40',
            className
          )}
        >
          {children}
        </div>
      </PromptInputContext.Provider>
    );
  }
);
PromptInput.displayName = 'PromptInput';

// ── PromptInputTextarea ───────────────────────────────────────────────────────
const PromptInputTextarea = ({ className, onKeyDown, disableAutosize = false, placeholder, ...props }) => {
  const { value, setValue, maxHeight, onSubmit, disabled } = usePromptInput();
  const textareaRef = useRef(null);

  useEffect(() => {
    if (disableAutosize || !textareaRef.current) return;
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height =
      typeof maxHeight === 'number'
        ? `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
        : `min(${textareaRef.current.scrollHeight}px, ${maxHeight})`;
  }, [value, maxHeight, disableAutosize]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
    onKeyDown?.(e);
  };

  return (
    <Textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      className={cn('text-base', className)}
      disabled={disabled}
      placeholder={placeholder}
      {...props}
    />
  );
};

// ── Recording waveform indicator ──────────────────────────────────────────────
const RecordingIndicator = () => (
  <div className="flex items-center gap-3 px-4 py-2">
    <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse shrink-0" />
    <div className="flex-1 h-8 flex items-center gap-0.5">
      {Array.from({ length: 28 }).map((_, i) => (
        <div
          key={i}
          className="w-0.5 rounded-full bg-white/40 animate-pulse"
          style={{
            height: `${Math.max(20, Math.sin(i * 0.7) * 60 + 50)}%`,
            animationDelay: `${i * 0.06}s`,
            animationDuration: `${0.5 + (i % 3) * 0.2}s`,
          }}
        />
      ))}
    </div>
    <span className="text-[11px] text-white/40 uppercase tracking-widest shrink-0">Écoute…</span>
  </div>
);

// ── Main AiPromptBox ──────────────────────────────────────────────────────────
/**
 * Props:
 *   onSend(message)       — called on submit
 *   isLoading             — streaming / loading state
 *   onAbort()             — called to stop generation
 *   placeholder           — textarea placeholder text
 *   value                 — controlled input value (optional)
 *   onValueChange(v)      — controlled input handler (optional)
 *   recording             — external recording state (optional)
 *   onToggleRecording()   — external STT toggle (optional)
 *   className             — extra CSS
 */
export const AiPromptBox = forwardRef((props, ref) => {
  const {
    onSend = () => {},
    isLoading = false,
    onAbort = () => {},
    placeholder = 'Interroger LoreKeeper...',
    className,
    value: externalValue,
    onValueChange: externalOnValueChange,
    recording: externalRecording,
    onToggleRecording,
  } = props;

  const [internalInput, setInternalInput] = useState('');
  const isControlled = externalValue !== undefined;
  const input = isControlled ? externalValue : internalInput;
  const setInput = isControlled ? (externalOnValueChange ?? (() => {})) : setInternalInput;

  const [internalRecording, setInternalRecording] = useState(false);
  const recording = externalRecording !== undefined ? externalRecording : internalRecording;

  const promptBoxRef = useRef(null);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;
    if (isLoading) return;
    onSend(trimmed);
    setInput('');
  }, [input, isLoading, onSend, setInput]);

  const handleMicClick = () => {
    if (onToggleRecording) {
      onToggleRecording();
    } else {
      setInternalRecording(p => !p);
    }
  };

  const hasContent = input.trim() !== '';

  const handleActionClick = () => {
    if (isLoading) { onAbort(); return; }
    if (recording) { handleMicClick(); return; }
    if (hasContent) { handleSubmit(); return; }
    handleMicClick();
  };

  return (
    <PromptInput
      value={input}
      onValueChange={setInput}
      isLoading={isLoading}
      onSubmit={handleSubmit}
      className={cn(
        'w-full bg-[#111111] border-[#2a2a2a] shadow-[0_8px_30px_rgba(0,0,0,0.5)] transition-all duration-300',
        recording && 'border-red-500/40',
        isLoading && 'border-[#F59E0B]/30',
        className
      )}
      // Only disable textarea during recording/loading — NOT the action button
      disabled={isLoading}
      ref={ref || promptBoxRef}
    >
      {/* Recording waveform OR textarea */}
      {recording ? (
        <RecordingIndicator />
      ) : (
        <PromptInputTextarea
          placeholder={placeholder}
          className="text-[15px] text-white/90 placeholder:text-white/25 leading-relaxed px-4 py-3"
        />
      )}

      {/* Bottom row — action button only */}
      <div className="flex items-center justify-end px-1 pt-1">
        {/* Main action button — never disabled so stop-dictation always works */}
        <button
          type="button"
          className={cn(
            'h-9 w-9 rounded-full flex items-center justify-center transition-all duration-200 shrink-0',
            isLoading
              ? 'bg-[#F59E0B]/10 border border-[#F59E0B]/30 text-[#F59E0B] hover:bg-[#F59E0B]/20'
              : recording
              ? 'bg-transparent border border-red-500/40 text-red-400 hover:bg-red-500/10'
              : hasContent
              ? 'bg-white text-black hover:bg-white/85 shadow-md active:scale-95'
              : 'bg-white/[0.05] border border-white/10 text-white/30 hover:bg-white/10 hover:text-white/60'
          )}
          onClick={handleActionClick}
        >
          {isLoading ? (
            <Square className="h-3.5 w-3.5 fill-current" />
          ) : recording ? (
            <StopCircle className="h-4 w-4" />
          ) : hasContent ? (
            <ArrowUp className="h-4 w-4" />
          ) : (
            <Mic className="h-4 w-4" />
          )}
        </button>
      </div>
    </PromptInput>
  );
});
AiPromptBox.displayName = 'AiPromptBox';
