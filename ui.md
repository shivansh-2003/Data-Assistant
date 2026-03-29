# UI — Remaining / Not Implemented

**Data Assistant Platform**  
**Version:** 2.1  
**Date:** February 2026  

This document lists only work that is **not yet implemented**. Everything else has been removed.

---

## Optional polish (by area)

- **Mobile refinements** — Bottom navigation for mobile, simplified mobile charts, mobile-specific modals, swipe gestures; target responsive coverage 90% (current ~70%).
- **Upload tab:** Custom drag-drop zone styling, processing animation.
- **Manipulation tab:** Per-item version details styling (beyond timeline list in card).
- **Visualization tab:** More ARIA on individual controls (beyond region labels).
- **Cards:** Optional more `glass-card` use.
- **Accessibility:** More ARIA labels on custom components; WCAG 4.1.2 Name, Role, Value currently partial (~60%). Target: full Level AA.

---

## Component / UI improvements needed

### Empty state

- **Dashboard tab (when implemented):** Use `render_empty_state()` for “no charts pinned”; chart cards as `card-interactive`; controls as `card-elevated`; drag-and-drop when built.

### Advanced data table

- **Current:** Basic Streamlit components.
- **Needed:** Wrapped in `card-elevated` with styled toolbar (search, filters, actions in a `.table-toolbar` div).

### Session pill

- **Current:** Plain caption for session indicator.
- **Needed:** Wrap in styled pill, e.g. `<div class="session-pill">` with consistent styling.

---

## Known limitations (unfixed)

### Streamlit constraints

- File uploader styling (limited customization).
- Column widths (can’t use exact pixels).
- Form submit button (always at bottom).
- Chat input (fixed positioning).
- Expander icons (can’t customize).  
**Workaround:** Work within Streamlit patterns. **Fix:** Accept or migrate to Reflex (Phase 4).

### Mobile experience

- **Missing:** Bottom navigation, simplified mobile charts, mobile-specific modals, swipe gestures.  
**Impact:** Desktop-first. **Effort:** ~4–6 hours.

### Performance

- **Further improvements:** Virtualized table rendering, chart lazy loading, graph simplification for large version histories.  
Pagination is in place for tables.

### Theme switching

- Theme change can require refresh in some cases (Streamlit state conflicts).  
**Fix:** Investigate Streamlit theme hooks.

---

## Future roadmap (not implemented)

### Phase 2: Enhanced components (3–4 weeks)

**Goal:** Component library for faster feature development.

| Task | Est. | Description |
|------|------|-------------|
| Status Badge Component | 2h | Reusable status indicator for API status, MCP status, processing states |
| Action Bar Component | 2h | Consistent action buttons for message/chart/data actions |
| Metric Card Component | 2h | Styled metric display for session info, data stats, performance |
| Toast Notification System | 4h | Non-intrusive success/error/warning notifications |
| Command Palette | 6h | Cmd/Ctrl+K; search across features; quick actions; recent files |
| Modal Component | 3h | Custom modal dialogs for confirmations, forms, previews |

**Total:** ~19 hours.

### Phase 3: Advanced features (4–6 weeks)

**Goal:** Exceed Julius.ai in unique ways.

| Task | Est. | Description |
|------|------|-------------|
| Dashboard Builder | 12h | Drag-and-drop canvas, chart resizing, grid snapping, layout templates, export/share |
| Collaborative Features | 16h | Share sessions via link, comments on charts, version annotations, export reports with narrative |
| Advanced Visualizations | 8h | Interactive sankey, network graphs, geospatial maps, 3D scatter |
| Smart Insights | 10h | Auto-detect anomalies, trend detection, correlation finder, insight cards |
| Performance Optimizations | 6h | Virtual scrolling, chart lazy loading, incremental loading, caching |
| Mobile-First Redesign | 8h | Bottom nav, mobile-optimized charts, touch gestures, simplified flows |

**Total:** ~60 hours.
