import Editor from '@monaco-editor/react';
import { useRef, useEffect } from 'react';

export default function CodeEditor({ code, onChange, activeLine }: any) {
  const editorRef = useRef<any>(null);
  const decorationsRef = useRef<any[]>([]);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
  };

  useEffect(() => {
    if (editorRef.current && activeLine) {
      decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, [
        {
          range: new (window as any).monaco.Range(activeLine, 1, activeLine, 1),
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
        defaultLanguage="python"
        theme="vs-dark"
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
