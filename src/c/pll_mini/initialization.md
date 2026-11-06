# Initialization Contract

## Requirements

| ID | Required Behavior |
| --- | --- |
| INIT-BASE | Preserve configured initialization, including standalone PLLs and unselected mux inputs; target reachability and SMT activity do not define initialization ownership. |
| EXCLUDE-SELF | Explicitly excluded nodes do not constrain, calculate or contribute register configuration. |
| EXCLUDE-BRANCH | Remove upstream nodes whose entire consumer set is removed by exclusion; do not remove other configured standalone nodes. |
| EXCLUDE-SHARED | An upstream node with any retained consumer stays configured. |
| WORD-COMPLETE | Merge all retained field contributors before whole-word writes; no mask or per-field read-modify-write. |
| EXTRA-INDEPENDENT | Extra registers remain explicit effects; extra-only words precede ordinary words, shared words merge once using existing override precedence. |
| PLUGIN-BOUNDARY | Common graph policy uses input relationships, not concrete node kinds. Plugins keep their own encoding and PLL sequences. |

These requirements are cumulative. Restoring INIT-BASE does not revoke EXCLUDE-BRANCH.
Historical output comparisons must distinguish deliberate exclusion from unrelated
standalone initialization and from underconstrained legal solver choices.

## Design

Before validation and solving, index configured input edges and consumer sets.
Start with explicitly excluded nodes. Remove their incoming consumer edges and
recursively remove parents only when their original nonempty consumer set has
become empty. A node with no original consumers is not removed just for being
standalone. A shared parent remains until its last consumer is removed. This is
linear in nodes and edges; no repeated whole-tree traversal or per-kind branches.

The resulting node graph owns constraints, fitted parameters and register plans.
The plan does not apply a second target-path filter. Register grouping sees every
remaining field before packing a word from zero. PLL staged writes are unchanged.
Explicit extras do not resurrect frequency nodes.

Plugins using a nonstandard input layout override `input_refs_from_config` for
raw dictionaries and validated objects. The default handles scalar or mapped
`source`; common normalization never branches on concrete node kinds.

## Examples And Counterexamples

- Standalone configured PLL: initialize it even with no clock target.
- Divider feeding only an excluded clock: no divider constraint or write.
- Same divider also feeding a retained clock: retain its configuration once.
- Two retained gates own bit 0 and bit 1: write 3, not 1.
- Exclude one of those gates explicitly: omit that contribution; do not silently
  retain its bit merely because the same register is written elsewhere.
- Exclude a branch and include an unrelated standalone PLL in the same input:
  omit only the branch. Neither blanket full-node generation nor blanket
  selected-target generation is correct.

Acceptance must reject both historical failure strategies under this same contract.
