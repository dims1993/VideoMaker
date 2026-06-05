import React from "react";

type JsonEditorProps = {
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  height?: string;
};

export function JsonEditor({ value, onChange, readOnly = false, height = "400px" }: JsonEditorProps) {
  return (
    <textarea
      spellCheck={false}
      readOnly={readOnly}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ height, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, monospace", fontSize: 12 }}
      className="w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800"
    />
  );
}

export default JsonEditor;
