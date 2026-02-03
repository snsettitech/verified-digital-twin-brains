## 2026-02-03 - [Invisible Text on Transparent Backgrounds]
**Learning:** Transparent backgrounds (e.g. `bg-emerald-500/10`) with fixed text colors (e.g. `text-white`) create accessibility failures when the underlying surface varies (e.g. white cards vs dark background). Relying on the app's global theme doesn't guarantee contrast for floating elements.
**Action:** For floating overlays like Toasts, use opaque/solid backgrounds that ensure contrast with the text regardless of what's behind them, or use a backdrop blur with sufficient opacity and adaptive text colors.
