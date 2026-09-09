# S5-V023-IMPL-311 browser evidence

The screenshots in this directory render the actual Workflow visual designer
implementation at visual checkpoint
`3a88cfb17af5e3a0b4f13ae100d4308787d75a01` (tree
`e4817bb9e9158dd1450d663b319d147ba79c8578`). They use the bounded Playwright
`TEST_ADAPTER` fixture in `workflow-visual-designer.spec.ts` so that the formal
Workflow and Skill response shapes are deterministic while the trusted 305
service path is unavailable in this worktree.

They prove layout and interaction presentation only. They do not prove the
trusted production identity journey, backend persistence, lifecycle authority,
execution, Workflow Run, Task Run, Attempt, success, latency, or runtime state.

- `workflow-designer-desktop.png`: desktop selected-node canvas and formal
  resource/operation details, with high-contrast catalog selection and visible
  canvas/detail controls.
- `workflow-designer-390px.png`: 390px catalog/workspace and
  canvas/list/detail navigation after a real in-browser edit/save/readback
  sequence against the test adapter. The test also checks that the save bar and
  product bottom navigation do not overlap.

Both images carry a visible `TEST_ADAPTER · INTERACTION EVIDENCE` badge.
