"use client";

export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print rounded-lg bg-ink px-4 py-2.5 text-[14px] font-semibold text-paper shadow-[3px_3px_0_0_var(--yellow)]"
    >
      Save as PDF
    </button>
  );
}
