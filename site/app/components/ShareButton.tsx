"use client";

import { useState } from "react";
import type { Grade } from "@/src/types/town";

interface ShareButtonProps {
  townName: string;
  grade: Grade;
  keyStat: string;
  url: string;
}

export default function ShareButton({
  townName,
  grade,
  keyStat,
  url,
}: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  const tweetText = `${townName} gets a ${grade ?? "incomplete"} on housing from MA Housing Report Card. ${keyStat} See the full breakdown: ${url}`;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(tweetText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers without clipboard API
      const ta = document.createElement("textarea");
      ta.value = tweetText;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <button
        onClick={handleCopy}
        className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded hover:bg-gray-700 transition-colors w-fit"
      >
        {copied ? (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
            Copied
          </>
        ) : (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
            Copy tweet
          </>
        )}
      </button>
      <p className="text-xs text-gray-500 font-mono bg-gray-50 p-3 rounded border leading-relaxed break-words">
        {tweetText}
      </p>
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Direct link:</span>
        <input
          readOnly
          value={url}
          className="text-xs text-gray-700 bg-gray-50 border rounded px-2 py-1 flex-1 min-w-0"
          onFocus={(e) => e.target.select()}
        />
      </div>
    </div>
  );
}
