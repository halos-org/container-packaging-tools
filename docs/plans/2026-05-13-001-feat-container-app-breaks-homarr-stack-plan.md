---
title: Inject conditional Breaks on the Homarr stack from container-packaging-tools
type: feat
status: active
date: 2026-05-13
origin: https://github.com/halos-org/halos/blob/main/docs/brainstorms/2026-04-28-homarr-relative-card-urls-requirements.md
---

# Inject conditional Breaks on the Homarr stack from container-packaging-tools

**Target repo:** `container-packaging-tools` (this repo). Cross-repo references to the `halos-org/halos` workspace are by GitHub URL; everything else is repo-relative to this repo's root.

## Overview

`container-packaging-tools` (CPT) v0.5.8 made generated container apps emit **path-only** Homarr card URLs (`url = "/signalk-server/"`) when they declare `routing:`. The path-only TOML form requires two consumers to be sufficiently new:

- `homarr-container-adapter (>= 0.4.6)` — `validate_app_url` accepts path-only.
- `halos-core-containers (>= 0.3.2)` — bundles the Homarr fork image v1.60.0-halos.1 whose `appHrefSchema` accepts path-only.

Without protection, a user on an older image who runs `apt install marine-avnav-container` (Cockpit App Store install, manual `apt install`, or any partial upgrade) gets the new path-only TOML on a system whose adapter+Homarr can't process it. **The card silently does not appear.** No error, no upgrade prompt, no signal.

This plan adds **conditional `Breaks:` clauses** to the .debs that CPT generates for routed/visible web apps. `Breaks: foo (<< X)` means *"if `foo` is installed and is older than X, this package cannot be installed alongside it"* — which causes apt to either auto-upgrade `foo` to satisfy the constraint, or refuse the install with a clear message. Crucially, `Breaks` does **not** force the broken-against package to be installed at all: a HaLOS device that doesn't run Homarr is unaffected.

Generator-injected (single source of truth in CPT) so future contract evolutions are one diff in the generator, not N diffs across every routed app's `metadata.yaml`.

## Problem Frame

The path-only-href migration was completed across the consumer side in early May:
- Homarr fork v1.60.0-halos.1 — schema accepts path-only.
- `homarr-container-adapter` v0.4.6 — registry validator accepts path-only; v0.4.7 — orphan-cleanup fix.
- `container-packaging-tools` v0.5.8 (today) — generator emits path-only TOMLs for routed apps.

The migration was rolled out by a cohort image build, in which every dependent ships together. That works for *image builds*. It does **not** work for *post-image installs*: HaLOS positions itself as an apt-installable distribution, the Cockpit App Store advertises individual app `apt install`, and `halos-marine-containers` packages are routinely added or upgraded à la carte. Partial-upgrade is part of the system's operational model.

Workspace policy [`halos/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md`](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md) lists *"manual partial upgrades are an expected operational pattern"* among the explicit "keep the pin" conditions. Marine container apps hit that condition; the cockpit-config precedent (which dropped the pin) did not, because cockpit-config is a base-system package that always upgrades in cohort.

The pin question splits into two sub-questions:
1. **Hard `Depends:` or conditional `Breaks:`?** A hard `Depends: halos-core-containers (>= 0.3.2)` would force every marine .deb install to also install halos-core-containers — wrong, because a user might run Signal K standalone without the Homarr dashboard. `Breaks:` is conditional: it constrains only when the named package *is* installed. The semantics match the requirement exactly.
2. **Per-app metadata or generator-injected?** Generator-injected (option A1 in the spec) because the *trigger condition* for needing the constraint is identical to the trigger condition for emitting a path-only TOML (`routing is not None and web_ui.enabled and web_ui.visible`). One source of truth, one update site for future evolutions.

## Requirements Trace

- **R1.** CPT-generated .debs for any routed, web-UI-enabled, visible app declare `Breaks: homarr-container-adapter (<< 0.4.6), halos-core-containers (<< 0.3.2)`.
- **R2.** Non-routed apps are unaffected — their generated `control` file gains no new `Breaks:` line.
- **R3.** App authors may still add app-specific `Breaks:` entries via `metadata.yaml`. The injected Homarr-stack breaks compose with (do not replace) any per-app declarations.
- **R4.** A future change to the Homarr-stack minimums (e.g., a v1.62 feature requirement) updates a single version constant in CPT, not every consuming repo.
- **R5.** The workspace policy doc is updated to clarify the cohort-only vs partial-upgrade distinction and the `Breaks`-vs-`Depends` choice for partial-upgrade scenarios.
- **R6.** Existing tests for the routed-URL emission continue to pass. New tests cover the `Breaks` injection trigger conditions and the rendered output.

## Scope Boundaries

- **In scope:** CPT schema + template_context + control.j2 template + tests + version bump + docs. Updating the workspace solutions doc.
- **Out of scope:** Re-bumping `halos-marine-containers` revisions to pick up the new generator (separate task; tracked as a follow-up in this plan).
- **Out of scope:** Adding runtime version probes to the adapter (a complementary defence layer; not required if `Breaks` is in place).
- **Out of scope:** Backfilling `Breaks` into `halos-cockpit-config` or other hand-packaged .debs that don't use CPT. Their cohort-only operational pattern still makes the pin redundant per the policy doc.
- **Out of scope:** Refactoring the existing `depends:`/`recommends:`/`conflicts:` schema fields. The new `breaks:` field is purely additive.

## Context & Research

### Relevant Code and Patterns

- `src/generate_container_packages/registry.py:107–119` — the routed branch that emits path-only `url`. The trigger condition for `Breaks` injection is the same condition that selected this branch.
- `src/generate_container_packages/template_context.py:303–340` — `_build_package_context` translates metadata.yaml fields into the Jinja context. `depends`, `recommends`, `suggests`, `provides`, `conflicts` are all formatted via `format_dependencies`. `breaks` would slot in identically.
- `src/generate_container_packages/templates/debian/control.j2` — the `Source: … / Package: …` template. Has conditional blocks for `recommends`, `suggests`, `provides`, `conflicts`. No `Breaks:` block yet; adding one is the same shape.
- `src/schemas/metadata.py:437–462` — Pydantic `AppMetadata` model with `depends`, `recommends`, `suggests`, `provides`, `conflicts`. `breaks: list[str] | None` field slots in next to `conflicts`.
- `tests/test_registry.py` — existing tests for `generate_registry_toml`. The injection logic lives in `template_context`, so new tests go in `tests/test_template_context.py` (existing file) and integration coverage in `tests/test_integration.py`.
- External: `halos-core-containers/debian/control` (a hand-packaged HaLOS .deb in a sibling repo) declares `Provides: halos-reverse-proxy` and `Conflicts: halos-reverse-proxy`. Demonstrates that the HaLOS ecosystem already uses Debian relationship semantics; CPT-generated apps are not setting a new precedent here.

### Institutional Learnings

- [Workspace policy: skip APT Depends pins between sibling HaLOS packages](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md) — the "drop the pin" three-layer test. This plan's case fails layer 1 (cohort upgrade is not the only access path) so the pin is required. The doc explicitly names *"manual partial upgrades are an expected operational pattern"* as a Keep condition.
- [Workspace learning: ship cross-format identity helper before URL migration](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-05-04-ship-cross-format-identity-helper-before-url-migration.md) — the SK-orphan post-mortem. Pattern: when a contract shape changes, the consumer must accept both shapes during the transition. Path-only acceptance was added in `homarr-container-adapter` v0.4.6; this plan ensures producers can't ship the new shape onto a pre-v0.4.6 consumer.

### External References

Debian Policy Manual §7.4 on `Breaks` (https://www.debian.org/doc/debian-policy/ch-relationships.html#packages-which-break-other-packages-breaks):
> When one binary package declares that it breaks another, dpkg will refuse to allow the package which declares Breaks to be unpacked unless the broken package is deconfigured first, and it will refuse to allow the broken package to be reconfigured.

apt resolves a `Breaks` constraint by **upgrading the broken-against package** to a version that satisfies the relationship, when one is available. If no satisfying version exists (or the user has held the package), apt aborts with a clear message naming the conflict.

`Breaks` is preferred over `Conflicts` when the relationship is *temporal* (a too-old version) rather than *fundamental* (irreconcilable functionality) — a conventional Debian distinction.

## Key Technical Decisions

- **Use `Breaks: foo (<< X)`, not `Depends: foo (>= X)`.** `Breaks` is conditional on `foo` being installed; `Depends` forces installation. A HaLOS device running Signal K without the Homarr dashboard would be over-constrained by `Depends`. Matches Debian policy guidance for "minimum version of an optional peer" scenarios.
- **Inject at the generator, not per-app.** The trigger condition (`routing is not None and web_ui.enabled and web_ui.visible`) is identical to the path-only-TOML emission condition. Same source of truth, single update site for future Homarr-stack contract changes. Lower bookkeeping debt than per-app `metadata.yaml` entries that have to be updated in every consumer repo when minimums change.
- **Hardcode the version constants in CPT.** `HOMARR_ADAPTER_MIN = "0.4.6"`, `HALOS_CORE_CONTAINERS_MIN = "0.3.2"` as module-level constants in `template_context.py` (or a small new `homarr_compat.py`). The values change rarely; a config file is over-engineering at this scale.
- **`breaks` schema field is additive.** Apps may declare their own `breaks:` list in `metadata.yaml`. The generator concatenates auto-injected Homarr-stack breaks with app-declared breaks. Order: auto-injected first, app-declared second, for predictable diffing.
- **Trigger condition matches TOML emission, not `routing` alone.** A non-visible routed app (`web_ui.visible: false`) is registered in the TOML registry but does not appear as a Homarr card. We could include the breaks unconditionally on `routing is not None`, but this would over-constrain hidden-routed apps. Use the same triple-condition that gates whether the adapter loads the TOML into Homarr.
- **`<<` strict-less-than, not `<=`.** `Breaks: foo (<< 0.4.6)` means "0.4.5 and earlier"; `0.4.6` itself is allowed (the first acceptable version).
- **Do not version-pin to upcoming `homarr-container-adapter` versions retroactively.** The constants are the minimums for the *current* contract shape (path-only TOML). If a future CPT change introduces a new contract requirement, that bump is done in a new CPT release with new constants — not silently moved here.

## Open Questions

### Resolved During Planning

- **Q: Inject via generator or require per-app declaration?** Generator. Trigger is the same as path-only-TOML emission; one source of truth.
- **Q: Use `Depends` or `Breaks`?** `Breaks`. Conditional on the peer being installed.
- **Q: What's the minimum `homarr-container-adapter` version?** `0.4.6` — first release that `validate_app_url` accepts path-only forms. Verified by inspecting `homarr-container-adapter/src/registry.rs::validate_app_url` history (commit `6482467 feat(adapter): accept and emit path-only URLs`, v0.4.6).
- **Q: What's the minimum `halos-core-containers` version?** `0.3.2` — first stable release pinning Homarr fork `v1.60.0-halos.1`. Verified by `git log -p -- docker-compose.yml` showing the pin change in commit `2b1be6a feat(homarr): promote fork v1.60.0-halos.1 to production`, which landed before the `0.3.0 → 0.3.1` bump and was released as `v0.3.2+1`.
- **Q: Does the Homarr fork ship as a separate .deb that should be the Break target instead of `halos-core-containers`?** No. `halos-core-containers` is a single hand-packaged .deb that bundles Traefik + Authelia + Homarr via a single `docker-compose.yml`. The Homarr image pin lives inside that .deb. Targeting `halos-core-containers` is the only correct apt-level option.
- **Q: Should non-routed (port-based) apps also gain `Breaks`?** No. Their generated TOML still uses `{{domain}}` (unchanged shape), so adapter v0.4.5 accepts it. They're not subject to the silent-card failure.
- **Q: Does the existing PR #171 still merge?** No — supersede. PR #171 only bumped revisions to push the path-only TOMLs through apt. After this plan executes, marine apps rebuild against CPT v0.6.0 and get `Breaks` lines too. A single marine rebuild after CPT v0.6.0 publishes covers both needs; #171's diff is included in the follow-up rebuild.

### Deferred to Implementation

- **Exact naming of the version-constant module.** Either inline in `template_context.py` or a new small `homarr_compat.py`. Whichever feels cleaner during implementation — both work. The constants don't change often enough to justify a config file or a JSON schema.
- **Test fixture choices.** Whether to extend `tests/fixtures/valid/full-app/metadata.yaml` or add a new `tests/fixtures/valid/routed-visible-app/`. Implementer decides based on test-readability.

## Implementation Units

- [ ] **Unit 1: Add `breaks` schema field + Homarr-stack auto-injection**

**Goal:** Extend the Pydantic metadata schema to accept `breaks: list[str] | None`, and add auto-injection logic in `_build_package_context` so routed visible apps get the Homarr-stack breaks lines without any per-app declaration.

**Requirements:** R1, R2, R3, R4

**Dependencies:** none

**Files:**
- Modify: `src/schemas/metadata.py` (add `breaks` field, mirror of `conflicts`)
- Modify: `src/generate_container_packages/template_context.py` (new constants, new context key `breaks`, injection logic in `_build_package_context`)
- Test: `tests/test_models.py` (schema acceptance)
- Test: `tests/test_template_context.py` (injection logic)

**Approach:**
- Add `HOMARR_ADAPTER_MIN_VERSION = "0.4.6"` and `HALOS_CORE_CONTAINERS_MIN_VERSION = "0.3.2"` as module constants.
- New helper `_compute_homarr_stack_breaks(metadata)` returns the auto-injected list when triple-condition holds (`routing is not None and web_ui.get("enabled") and web_ui.get("visible")`), else empty list.
- In `_build_package_context`, the new `breaks` context value is the concatenation of `_compute_homarr_stack_breaks(metadata)` and `metadata.get("breaks", [])`, formatted via `format_dependencies`.
- Auto-injected entries come first for predictable output ordering.
- Trigger condition uses `.get()` lookups (not Pydantic attribute access) for parity with the existing template_context code which receives a dict.

**Patterns to follow:**
- `_build_package_context` lines 303–340 — same shape as how `depends`/`recommends`/`conflicts` are formatted.
- Pydantic field declaration style — match the existing `conflicts` field (line 456) verbatim except for description text.

**Test scenarios:**
- Happy path: metadata with `routing: {auth: {mode: none}}`, `web_ui: {enabled: true, visible: true, ...}` — context's `breaks` string contains both `homarr-container-adapter (<< 0.4.6)` and `halos-core-containers (<< 0.3.2)`.
- Happy path: same metadata plus a user-declared `breaks: ["foo-package (<< 1.0)"]` — output is auto-injected entries first, then `foo-package (<< 1.0)`.
- Edge case: no `routing` key — context's `breaks` string is empty (auto-injection does NOT fire).
- Edge case: `routing` present but `web_ui.enabled: false` — empty (auto-injection does NOT fire; matches the path-only-TOML emission condition).
- Edge case: `routing` present, `web_ui.enabled: true`, `web_ui.visible: false` — empty (consistent with the registry TOML not being installed for adapter consumption).
- Edge case: routed visible app with `breaks: null` (explicit None) — auto-injected entries only, no error.
- Error path: `breaks` field given a non-list value in metadata — Pydantic raises `ValidationError`.
- Schema acceptance: `AppMetadata(..., breaks=["pkg (<< 1.0)"])` round-trips.

**Verification:**
- `uv run pytest tests/test_template_context.py tests/test_models.py -v` — all new scenarios pass.
- Manual: load an existing fixture with `routing+web_ui+visible`, inspect the context dict, confirm `breaks` key is populated as expected.

- [ ] **Unit 2: Render `Breaks:` line in control.j2 template**

**Goal:** Emit a `Breaks:` line in the generated Debian control file when the context's `breaks` value is non-empty.

**Requirements:** R1, R2, R6

**Dependencies:** Unit 1

**Files:**
- Modify: `src/generate_container_packages/templates/debian/control.j2`
- Test: `tests/test_renderer.py` (template output for the new Jinja block)
- Test: `tests/test_integration.py` (end-to-end `generate_container_packages` invocation verifies the generated control file)

**Approach:**
- Add a conditional `{% if package.breaks %}Breaks: {{ package.breaks }}{% endif %}` block in the Package stanza, placed adjacent to the existing `Conflicts:` block for symmetry.
- Keep the line break placement consistent with neighbouring blocks so generated output is diff-stable.

**Patterns to follow:**
- Existing `Conflicts:` block in `control.j2` (verbatim shape; same conditional + same indentation).

**Test scenarios:**
- Happy path: context with `breaks = "homarr-container-adapter (<< 0.4.6), halos-core-containers (<< 0.3.2)"` — rendered control contains `Breaks: homarr-container-adapter (<< 0.4.6), halos-core-containers (<< 0.3.2)` on its own line.
- Edge case: context with `breaks = ""` (empty) — rendered control contains no `Breaks:` line at all (not `Breaks:` with empty value).
- Integration: full pipeline invocation on a routed visible fixture — emitted `debian/control` file contains the expected `Breaks:` line; emitted `etc/halos/webapps.d/*.toml` has path-only `url` (unchanged from v0.5.8 behavior).
- Integration: full pipeline on a non-routed fixture — no `Breaks:` line in control (unchanged from v0.5.7).
- Output stability: rendering the same context twice produces byte-identical control files.

**Verification:**
- `uv run pytest tests/test_renderer.py tests/test_integration.py -v` — all scenarios pass.
- Manual: build a fixture .deb via `./run build` in Docker, extract with `ar x` + `tar`, `cat control` shows the new line.

- [ ] **Unit 3: Bump CPT version and prepare release**

**Goal:** Bump CPT from `0.5.8` to `0.6.0` (minor — new `breaks` schema field + new auto-injection behavior is a backward-compatible feature, not a patch), ensure the diff is releasable, run the full Pre-Push Requirements checklist mandated by `AGENTS.md`. Use `./run bumpversion minor`.

**Requirements:** R6

**Dependencies:** Units 1 + 2 merged or staged.

**Files:**
- Modify: `VERSION`, `pyproject.toml`, `src/generate_container_packages/__init__.py`, `.bumpversion.cfg` (auto-handled by `./run bumpversion patch`)
- Modify: `uv.lock` (regenerated)

**Approach:**
- Standard `./run bumpversion patch` workflow per AGENTS.md.
- Pre-push checklist (mandatory): `./run lint && ./run check-format && uvx ty check src/ && uv run pytest tests/test_*.py -m "not integration and not install" -q && uv run pytest tests/test_*.py -m "integration and not install" -q`.

**Test expectation:** none — version bump only, no behavioural change.

**Verification:**
- All Pre-Push checks pass locally (matches what CI will run on the PR).
- PR opened against `halos-org/container-packaging-tools`, CI green on `checks / lintian`, `checks / tests`, `checks / version-bump-check`, `checks / version-check`.
- After merge: Main Branch CI/CD produces `v0.6.0+1_pre` (auto) and `v0.6.0+1` draft; publishing the draft as Latest fires the apt pipeline.

- [ ] **Unit 4: Documentation — update workspace policy doc and CPT docs**

**Goal:** Update the workspace policy doc (`halos-org/halos`) to record the partial-upgrade clause that flipped this case from "drop the pin" to "use `Breaks:`". Add a brief note to this repo's `AGENTS.md` explaining the auto-injection rule for future contributors.

**Requirements:** R5

**Dependencies:** Units 1–3 (so the doc can reference the released version).

**Files:**
- Modify (in `halos-org/halos`): `docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md` (add an Example section: "When CPT auto-injects `Breaks:` for routed visible apps"). This is a separate PR in the workspace repo.
- Modify (in this repo): `AGENTS.md` (one-paragraph note + link back to the workspace solutions doc).

**Approach:**
- Solutions doc update is additive: add a worked example after the existing examples showing that routed apps installable individually (Cockpit App Store, raw `apt install`) fail the cohort-upgrade test and gain `Breaks` rather than `Depends`. Keep the existing cockpit-config example as the cohort-only counter-case.
- CPT AGENTS.md note documents the two version constants and the trigger condition, so a future maintainer bumping the constants knows where to look.

**Test expectation:** none — documentation only.

**Verification:**
- Markdown lints cleanly (if lefthook checks markdown — verify locally).
- Cross-reference back from CPT AGENTS.md to the solutions doc works.
- The solutions doc's "Examples" section now covers both directions (drop the pin / inject the pin) so a future PR author can find the right precedent in one read.

## System-Wide Impact

- **Interaction graph:** CPT-generated .debs gain a new outbound relationship to two HaLOS-internal packages. apt's solver handles the resolution.
- **Error propagation:** When a user installs a routed marine app onto a system with adapter v0.4.5 or `halos-core-containers` v0.3.1, apt will report e.g.
  ```
  The following packages have unmet dependencies:
   marine-avnav-container : Breaks: homarr-container-adapter (< 0.4.6) but 0.4.5-1 is installed
  ```
  and either auto-resolve by upgrading the broken-against package (if a satisfying version is in `apt.halos.fi`) or refuse cleanly with the message above. **Either outcome is correct** — no silent missing card.
- **State lifecycle risks:** None new. The `Breaks` constraint is metadata-only; no scripts run, no state migrated.
- **API surface parity:** The `breaks:` field is new in `metadata.yaml`. Apps that don't declare it are unaffected (default `None`). Existing tests that don't exercise it are unaffected.
- **Integration coverage:** Unit 2's integration test covers the end-to-end generator → control file pipeline. Test scenarios in Unit 1 cover the trigger-condition decision matrix.
- **Unchanged invariants:** The path-only URL emission from registry.py is unchanged (CPT v0.5.8's behavior is preserved). The `depends`/`recommends`/`suggests`/`provides`/`conflicts` fields are unchanged. Non-routed apps generate identical control output to v0.5.8.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Future Homarr-fork release tightens the path-only contract further (e.g., requires a new field), but CPT constants are stale → silent failures resume. | Document in CPT AGENTS.md that bumping these constants is part of any future Homarr-stack contract change. Add a brief checklist line to the release-promotion runbook. |
| `Breaks` syntax error in template → all CPT-generated .debs fail to build until reverted. | Unit 2's integration test catches malformed `Breaks:` lines before merge; lintian (run in marine CI) flags invalid relationship syntax. |
| `halos-core-containers` is renamed or split — the `Breaks` target becomes wrong. | Constants live in one file; rename is a single grep-and-replace in CPT followed by a normal release. Same blast radius as a per-app rename would have. |
| A user pins `homarr-container-adapter` (apt-mark hold) at v0.4.5 — install of new marine app aborts with `Breaks` error. | Correct behavior. Better than silent missing card. The error message names the held package; user can `apt-mark unhold` or accept the install refusal. |
| Marine maintainers rebuild against an older CPT (e.g., pinned `TOOLS_REF` in their build script) and don't get the `Breaks` lines. | The marine build script defaults to CPT `main` branch (no version pin). Document the requirement in CPT AGENTS.md. Detection: lintian or a CI smoke-test that asserts the `Breaks:` line is present in routed-app .debs (deferred — not required for first release). |
| Migration window: between CPT v0.6.0 publish and marine rebuild, marine apps still ship path-only TOMLs without `Breaks`. | Sequence the rollout: publish CPT v0.6.0 → rebuild marine → publish marine. The window is the same as today (during this work the marine package on apt has path-only TOMLs without `Breaks`); the plan tightens it rather than introducing it. |

## Documentation / Operational Notes

- **Workspace policy doc update** (Unit 4) is the durable record. Future PR authors hitting the same question will find the partial-upgrade clause and the `Breaks`-vs-`Depends` decision documented.
- **No runbook changes** for image builds — CPT is pulled from git main during marine build, so the next marine rebuild after CPT v0.6.0 publishes naturally picks up the change.
- **No device-side changes** — `Breaks` is metadata; no postinst scripts, no migrations.

## Follow-ups (Out of Scope for This Plan)

1. **Marine rebuild.** After CPT v0.6.0 publishes, supersede `halos-org/halos-marine-containers#171` with a new revision-bump PR (or just close + retrigger CI). Verify the generated .debs contain the expected `Breaks:` lines by extracting one and grepping the control file. Publish the resulting draft. Then proceed with the halos-pi-gen image rebuild as already planned.
2. **`halos-imported-containers` impact.** Verify whether any apps there declare `routing:` + `web_ui.visible`. Today's spot-check found none, but a future imported app could need the same `Breaks`. CPT auto-injection handles it transparently once the imported repo rebuilds against v0.6.0.
3. **Runtime probe in `homarr-container-adapter`.** A long-term improvement: have the adapter detect at runtime whether the Homarr peer supports path-only and log a clear warning if not. With `Breaks` in place, this is a defence-in-depth nicety, not a requirement.
4. **Optional CI smoke-test.** A check that every routed-visible CPT-generated .deb in the apt repo contains the expected `Breaks:` line. Catches the "marine build pinned to an old CPT" failure mode. Implement only if the failure mode actually surfaces in practice.

## Sources & References

- **Origin document (workspace):** [halos/docs/brainstorms/2026-04-28-homarr-relative-card-urls-requirements.md](https://github.com/halos-org/halos/blob/main/docs/brainstorms/2026-04-28-homarr-relative-card-urls-requirements.md)
- **Workspace policy:** [halos/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md)
- **CPT generator source (this repo):** `src/generate_container_packages/template_context.py`, `src/generate_container_packages/templates/debian/control.j2`, `src/schemas/metadata.py`
- **Triggering PR (this work's parent):** [halos-org/container-packaging-tools#202](https://github.com/halos-org/container-packaging-tools/pull/202) — path-only URL emission, merged 2026-05-13.
- **In-flight blocker PR:** [halos-org/halos-marine-containers#171](https://github.com/halos-org/halos-marine-containers/pull/171) — supersede after CPT v0.6.0 publishes.
- **Debian Policy Manual §7.4:** https://www.debian.org/doc/debian-policy/ch-relationships.html#packages-which-break-other-packages-breaks
- **Related cross-repo learning** (lives in `halos-org/homarr-container-adapter`, not the workspace): [`docs/solutions/best-practices/2026-05-04-ship-cross-format-identity-helper-before-url-migration.md`](https://github.com/halos-org/homarr-container-adapter/blob/main/docs/solutions/best-practices/2026-05-04-ship-cross-format-identity-helper-before-url-migration.md) — accept-both-shapes during a contract migration.
