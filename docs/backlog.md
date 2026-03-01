# Backlog — Known Issues & Future Improvements

> Issues noticed during testing that are not blocking current progress.
> Format: ## [BL-ID] Title

---

## BL-01: Mirror Reflections Detected as Real People

**Observed:** The YOLO detector tracks people visible in gym mirrors as separate persons, assigning them their own track IDs. A person exercising near a mirror produces 2+ tracks — one for the real person and one (or more) for their reflection.

**Impact:** Inflated person counts, duplicate rep counting events, wasted inference on ghost tracks.

**Possible fixes (to evaluate later):**
- Camera placement guidelines to avoid mirror angles in the frame
- Homography-based floor projection: reflections have no valid floor position (they appear "behind the wall") — filter tracks whose projected floor position falls outside the gym boundary polygon
- Reflection-specific heuristics: reflections are horizontally mirrored, move in lockstep, and appear at symmetric positions — could be detected via pairwise track comparison
- Train a lightweight binary classifier on person crops to distinguish real vs. mirrored appearance

**Suggested approach:** Floor-plan homography filter (Phase 3 feature) is the most principled solution. Pair it with camera placement guidelines as a short-term mitigation.

**Priority:** Medium — does not block Phase 1 but affects rep counting accuracy in mirror-heavy gyms.

**Discovered:** 2026-02-28, during first live visualizer test.
