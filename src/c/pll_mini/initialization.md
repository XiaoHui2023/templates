# Initialization Contract

## Requirements

| ID | Required Behavior |
| --- | --- |
| INIT-BASE | Preserve configured initialization, including standalone PLLs and unselected mux inputs; target reachability and SMT activity do not define initialization ownership. |
| EXCLUDE-SELF | Explicitly excluded nodes do not constrain, calculate or contribute register configuration. |
| EXCLUDE-BRANCH | Remove upstream nodes whose entire consumer set is removed by exclusion; do not remove other configured standalone nodes. |
| EXCLUDE-SHARED | An upstream node with a retained effective consumer or its own frequency demand stays configured. |
| WORD-COMPLETE | Merge all retained field contributors before whole-word writes; no mask or per-field read-modify-write. |
| EXTRA-INDEPENDENT | Extra registers remain explicit effects; extra-only words precede ordinary words, shared words merge once using existing override precedence. |
| PLUGIN-BOUNDARY | Common graph policy uses input relationships, not concrete node kinds. Plugins keep their own encoding and PLL sequences. |
| TERMINAL-DEMAND | Passive unconstrained terminals do not preserve upstream controls, including after physical target deletion; real demand through transparent chains does. |
| INIT-EFFECT | A node's own observable demand protects it at both original terminals and terminals exposed by pruning. A register-backed gate remains an initialization root. |
| INIT-INTENT | Explicit programmable initialization values and input selections constrain even inactive controls; equal frequency does not permit substituting another required source. |
| INIT-TARGET | A required target must not be explicitly excluded in the input. Restore its intended inclusion, never change arithmetic to compensate for deletion. |
| REGISTER-REPLAY | Check required field values and selected source identity against final programmed words, not just frequency or agreement with the generated array. |

These requirements are cumulative. Restoring INIT-BASE does not revoke EXCLUDE-BRANCH.
Historical output comparisons must distinguish deliberate exclusion from unrelated
standalone initialization and from underconstrained legal solver choices.

## Design

Before validation and solving, index configured input edges and consumer sets.
Start with explicitly excluded nodes and passive leaves without terminal demand.
Remove their incoming consumer edges and
recursively remove parents only when their original nonempty consumer set has
become empty and they have no observable demand of their own. A node with no original consumers is not removed just for being
standalone if it has an initialization effect. A shared parent remains until its
last effective consumer disappears. Empty transparent chains collapse through
the same worklist, even without an explicit exclude flag. This is
linear in nodes and edges; no repeated whole-tree traversal or per-kind branches.

The resulting node graph owns constraints, fitted parameters and register plans.
The plan does not apply a second target-path filter. Register grouping sees every
remaining field before packing a word from zero. PLL staged writes are unchanged.
Explicit extras do not resurrect frequency nodes.

Plugins using a nonstandard input layout override `input_refs_from_config` for
raw dictionaries and validated objects. The default handles scalar or mapped
`source`; common normalization never branches on concrete node kinds.

`terminal_demand_from_config` declares a node's own observable demand. The same
cached predicate applies to original leaves and ancestors exposed by pruning.
`standalone_initialization` separately preserves legacy independent initialization
only for nodes with no original consumers; it does not protect emptied branches.
Transparent plugins require a frequency anchor; clock plugins treat omitted and
negative frequencies as unconstrained. Gates with a register have an explicit
initialization effect. An inverter's accepted `reg` metadata does not imply a
write. Other effectful plugins override this hook. Malformed anchors remain
for normal validation. This is not a solver-activity or selected-path filter.

`frequency_demand_from_config` independently declares an explicit frequency
anchor. Such an anchor survives removal of passive downstream nodes; standalone
initialization alone does not protect a formerly consumed, now unused branch.

## Explicit Programming Intent

For programmable quotient nodes, `init_ratio` fixes the value to program and
requires `regs`. For muxes, `init_sel` fixes the input number to program and
requires `reg`. These are unconditional solver constraints and own demand, even
when their downstream has been removed or their arm is not selected. Existing
`ratio` and `sel` still describe non-programmed fixed hardware and cannot coexist
with their corresponding initialization field. Invalid ranges, missing writable
registers, conflicting fixed settings and absent input numbers fail with the node
name. Shared-field and field-width constraints remain applicable.

Omitting initialization intent preserves the existing frequency-driven search;
an arbitrary legal model is not a specified hardware default. Required source
identity and backup values must come from the input author, not frequency equality.
Explicit `exclude` still takes precedence over all initialization intent.

## Examples And Counterexamples

- Standalone configured PLL: initialize it even with no clock target.
- Divider feeding only an excluded clock: no divider constraint or write.
- Same divider also feeding a retained clock: retain its configuration once.
- Delete or exclude that clock, leaving only an unconstrained cell or transparent
  chain: omit the chain and exclusive divider; references alone are not demand.
- Add a real frequency target after the chain: retain the complete shared upstream.
- A frequency-constrained cell or divider followed only by a passive cell: remove
  the passive child, but preserve the anchor and its upstream configuration.
- Two retained gates own bit 0 and bit 1: write 3, not 1.
- Exclude one of those gates explicitly: omit that contribution; do not silently
  retain its bit merely because the same register is written elsewhere.
- Exclude a branch and include an unrelated standalone PLL in the same input:
  omit only the branch. Neither blanket full-node generation nor blanket
  selected-target generation is correct.

Acceptance must reject both historical failure strategies under this same contract.

## Initialization Example

`example/initialization.yaml` programs two equal-rate inputs with distinct source
identity. `required_clock` selects `alternate` through input 1; `required_backup`
uses `primary / 4`. Both targets are enabled. The standalone DTO programs ratio 8
and the standalone mux programs input 7 even without an active downstream target.
The register-backed gate remains configured when its passive child is removed.
Only `removed_clock` is deliberately excluded, taking its exclusive divider out
of initialization. Independent clock demand remains available.

With the supplied `normal.ralf`, the complete ordinary writes are:

| Address | Value | Meaning |
| --- | --- | --- |
| 0xd10 | 0x1 | Extra-only enable, emitted first |
| 0x500 | 0x303 | Divider ratio 4, reset released and load asserted |
| 0x530 | 0x20000003 | DTO ratio 8, reset released and load asserted |
| 0x600 | 0x1 | Retained gate open |
| 0xd00 | 0x3 | Both configured gate fields merged |
| 0x504 | 0x1 | Required source is alternate, not equal-rate primary |
| 0xd08 | 0x7 | Standalone source selection |

Each address occurs once. Address 0x520 (the excluded branch divider) is absent.
Changing a required target to `exclude: true` is not a valid way to preserve this
example's requirements, even if explicit initialization leaves the same write
values. Restore required targets individually; do not change divider equations.
