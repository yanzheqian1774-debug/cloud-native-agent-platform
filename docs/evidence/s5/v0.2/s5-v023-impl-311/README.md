# S5-V023-IMPL-311 browser evidence

The screenshots in this directory render the actual Workflow visual designer
implementation at the task branch head. They use the bounded Playwright
`TEST_ADAPTER` fixture in `workflow-visual-designer.spec.ts` so that the formal
Workflow and Skill response shapes are deterministic while the trusted 305
service path is unavailable in this worktree.

They prove layout and interaction presentation only. They do not prove the
trusted production identity journey, backend persistence, lifecycle authority,
execution, Workflow Run, Task Run, Attempt, success, latency, or runtime state.

- `workflow-designer-desktop.png`: desktop selected-node canvas and formal
  resource/operation details.
- `workflow-designer-390px.png`: 390px list/config navigation after a real
  in-browser edit/save/readback sequence against the test adapter.
