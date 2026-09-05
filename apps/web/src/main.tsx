import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="flex min-h-svh items-center justify-center bg-stone-50 px-6 py-16 text-stone-900">
      <section aria-labelledby="title" className="w-full max-w-xl border-t border-stone-300 pt-8">
        <span className="inline-block rounded-full border border-stone-300 px-3 py-1 text-xs font-medium tracking-widest text-stone-600">
          BOOTSTRAP
        </span>
        <h1 id="title" className="mt-8 text-5xl font-semibold tracking-tight sm:text-6xl">QUALOR</h1>
        <p className="mt-4 text-lg text-stone-600">Autonomous Opportunity Intelligence</p>
        <p className="mt-12 text-sm text-stone-600">Development foundation ready.</p>
      </section>
    </main>
  </StrictMode>,
);
