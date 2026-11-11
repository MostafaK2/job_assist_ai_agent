"use client";

import { useRef, useState } from "react";
import { MAX_RESUME_MB, uploadResume } from "@/lib/onboarding";

export default function ResumeUpload({ onDone }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | reading
  const [error, setError] = useState(null);

  async function handleFile(file) {
    if (!file) return;
    setError(null);
    // Quick checks here; the backend checks the real file content again.
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      return setError("Upload a PDF. Export it from Word or Google Docs if needed.");
    }
    if (file.size > MAX_RESUME_MB * 1024 * 1024) {
      return setError(`That file is over ${MAX_RESUME_MB} MB. Upload a smaller PDF.`);
    }

    setStatus("reading");
    try {
      const { upload_id, resume } = await uploadResume(file);
      onDone({ uploadId: upload_id, resume, filename: file.name });
    } catch (e) {
      setError(e.message);
      setStatus("idle");
    }
  }

  if (status === "reading") {
    return (
      <div role="status" className="rounded-xl border border-line bg-surface p-10 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-line border-t-ink motion-reduce:animate-none" />
        <p className="mt-4 font-medium">Reading your resume…</p>
        <p className="mt-1 text-sm text-muted">This usually takes a few seconds.</p>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        className={`rounded-xl border-2 border-dashed p-10 text-center ${
          dragging ? "border-ink bg-surface" : "border-line bg-surface/60"
        }`}
      >
        <p className="text-lg font-medium">Drop your resume here</p>
        <p className="mt-1 text-sm text-muted">PDF only, up to {MAX_RESUME_MB} MB</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-5 rounded-md bg-ink px-5 py-2.5 font-medium text-white"
        >
          Choose a file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
      </div>
      {error && <p role="alert" className="mt-3 text-stop">{error}</p>}
      <p className="mt-4 text-sm text-muted">
        Your resume is only used to fill in your profile and your applications.
      </p>
    </div>
  );
}