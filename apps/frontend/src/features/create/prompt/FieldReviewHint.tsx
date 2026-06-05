export function FieldReviewHint({ pending }: { pending: boolean }) {
  if (!pending) return null;
  return (
    <span
      className="inline-flex items-center rounded-md border border-violet-300/80 bg-violet-100/90 px-1.5 py-0.5 text-[10px] font-medium text-violet-800"
      title="Valor sugerido por el análisis de transcripciones. Revísalo antes de guardar el template."
    >
      inferido — revisa antes de guardar
    </span>
  );
}

export function fieldReviewClass(pending: boolean): string {
  return pending ? "ring-1 ring-violet-300/70 border-violet-200" : "";
}
