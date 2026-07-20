import Editor from '@monaco-editor/react';
import { useRef, useEffect } from 'react';
import { useSettings } from '@/contexts/SettingsContext';

export default function CodeEditor({ code, onChange, activeLine, onRun, language }: any) {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<any[]>([]);
  const { settings } = useSettings();

  const currentLanguage = language || settings.language || 'python';

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Define custom themes
    monaco.editor.defineTheme('dracula', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { background: '282a36' },
        { token: 'keyword', foreground: 'ff79c6', fontStyle: 'bold' },
        { token: 'identifier', foreground: 'f8f8f2' },
        { token: 'string', foreground: 'f1fa8c' },
        { token: 'comment', foreground: '6272a4' },
      ],
      colors: { 'editor.background': '#282a36' }
    });

    monaco.editor.defineTheme('monokai', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { background: '272822' },
        { token: 'keyword', foreground: 'f92672' },
        { token: 'string', foreground: 'e6db74' },
        { token: 'comment', foreground: '75715e' },
      ],
      colors: { 'editor.background': '#272822' }
    });

    monaco.editor.defineTheme('light', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: { 'editor.background': '#ffffff' }
    });

    // Auto-run on paste
    editor.onDidPaste(() => {
      if (settings.autoRunOnPaste && onRun) {
        onRun();
      }
    });
  };

  useEffect(() => {
    if (editorRef.current && monacoRef.current && activeLine) {
      decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, [
        {
          range: new monacoRef.current.Range(activeLine, 1, activeLine, 1),
          options: {
            isWholeLine: true,
            className: 'bg-blue-500/20 border-l-4 border-blue-500',
            glyphMarginClassName: 'bg-blue-500',
          }
        }
      ]);
    } else if (editorRef.current) {
      decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, []);
    }
  }, [activeLine]);

  return (
    <>
      <style>{`.bg-blue-500\\/20 { background-color: rgba(59, 130, 246, 0.2) !important; border-left: 4px solid #3b82f6 !important; }`}</style>
      <Editor
        height="100%"
        language={currentLanguage}
        theme={settings.editorTheme}
        value={code}
        onChange={onChange}
        onMount={handleEditorDidMount}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: 'JetBrains Mono, monospace',
          padding: { top: 16 },
          scrollBeyondLastLine: false,
        }}
      />
    </>
  );
}
