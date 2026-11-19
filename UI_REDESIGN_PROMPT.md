# UI redesign brief (for the coding agent)

The app already runs at http://127.0.0.1:8000. Redesign the **Clips** screen so it is **visual first**. Attach the reference screenshots the user provides (a commercial clipping tool's clip grid and length selector) and use them only for layout ideas. Do **not** copy their logo, name, colors, icons or text. Keep the app's own look.

## 1. Clip length selector (before "Make clips")
A row of chips, single select:
- Auto (default, under 90 s)
- Under 30 s  -> target 15 to 30 s
- 30 to 60 s  -> target 30 to 60 s
- 60 to 90 s  -> target 60 to 90 s
- Over 90 s   -> target 90 to 180 s
Send `min_len` and `max_len` to `POST /api/clip`. The pipeline must respect them, and the UI shows the chosen range on every card. Keep "Top N" next to it.

## 2. Ranked clips as a video grid, not text rows
- Responsive grid of cards (4 across on desktop, 2 on tablet, 1 on phone). No horizontal scrolling anywhere.
- Each card shows a **9:16 video thumbnail** (poster frame from the middle of the clip, extracted with ffmpeg), not a text row.
- Over the thumbnail: rank badge `#1`, `#2`... top-left; duration chip (`0:42`) top-right; centered play button; the **burned caption in its real style** along the bottom.
- Hover or tap plays the clip muted in a loop. Click opens the full player and editor in a side drawer.
- Under the thumbnail: big score `94/100`, a 5-segment mini bar (hook, chat, emotion, story, trend), the AI title (one line), and a row of icon buttons: Edit/trim, Reframe, Captions, Download, Schedule. Every icon button has an `aria-label` and a tooltip.
- Sort control: Highest score (default), Newest, Longest, Shortest. "Select all" plus per-card checkbox, with bulk actions: Download, Schedule.
- Every clip has a unique, specific title. Never show the same title twice.
- Skeleton cards while clips are rendering, with a progress bar per stage (download, transcribe, rank, cut).

## 3. Show how captions will look
- Caption style picker is a row of **visual tiles**. Each tile shows a sample word in that style (font, color, outline or box, highlighted word) on a dark sample frame. No plain dropdown.
- Styles: Karaoke Pop (white with yellow active word), Clean White (white with soft shadow), Bold Box (white text on a solid accent box). Define each style once as JSON (font, size, colors, outline, position, active-word color) and use the same JSON for the live preview and the ffmpeg burn-in, so what the user sees is what gets rendered.
- The editor drawer shows the live preview: the caption text plays word by word in sync with the video using the word timestamps.
- Editing caption text updates the preview immediately.
- Hook overlay (first 2 seconds) is previewed too.

## 4. Layout and fixes
- Dark UI is fine and preferred for video-first screens. Keep text contrast at 4.5:1 or better.
- Fix the panel that was cut off at the right edge in the current build.
- Test with a real 5 to 10 minute video, not color bars. Make sure scores differ between clips and clips respect the chosen length.

## Check
Open the app in the browser, process a real video, choose "30 to 60 s", and take screenshots showing: the length chips, the video grid with ranks and scores, a card with live-styled captions, and the style tiles. Report anything that did not work.

## 5. Clip editor screen (opens from a card)
Reference screenshots show two editors: one with a left tool rail, big preview and trim timeline; one with a caption list on the left, preview in the middle, and a caption template gallery on the right. Build the app's own version, original look.

Layout (dark, full screen, no page scroll):
- Top bar: back arrow, clip title (editable), "Saved" status, Export button (renders mp4).
- Left tool rail: Captions (default), Templates, Trim, Reframe, Hook, Thumbnail.
- Left panel, Captions: toggle **Words | Lines**. A list of caption lines. Each line shows its start and end time and its words as chips; click a word to edit it, the word being spoken is highlighted. Buttons: Regenerate captions, Import SRT.
- Center: the video preview at the chosen ratio with the caption rendered in the selected style, synced word by word. Below it: ratio buttons (9:16, 1:1, 4:5, 16:9), Fit / Crop to face toggle, play button and time.
- Right panel, **Caption templates**: a gallery of **10 visual templates** in a 2-column grid. Each tile is a real thumbnail of the template (sample text styled exactly as it will render), with its name. Clicking a tile applies it live to the preview. Templates: Pop, Clean, Box, Neon, Outline, Comic, Minimal, Highlight, Gradient, Typewriter. Each template is one JSON style (font, size, weight, fill, stroke, shadow or glow, background box, active-word color, position, animation) shared by the preview and the ffmpeg burn-in.
- Bottom timeline: thumbnail strip of the clip with draggable trim handles, a row of word blocks under it aligned to the audio, and a zoom slider.
- Undo and redo for edits. Autosave to `data/state.json`.
Check: edit a word, switch template, change ratio, trim, export, and play the exported file to confirm the burned captions match the preview.
