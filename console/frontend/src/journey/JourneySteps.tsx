const steps = ["理解问题", "确认目标", "制定方案", "执行", "验收结果"];

export function JourneySteps({ current, executionAvailable=false }: { current: 1 | 2 | 3 | 4 | 5; executionAvailable?:boolean }) {
  return <ol className="journey-steps" aria-label="当前阶段">{steps.map((label, index) =>
    <li key={label} className={index + 1 < current ? "is-complete" : ""} aria-disabled={(index > 2 && !executionAvailable) || undefined} aria-current={index + 1 === current ? "step" : undefined}>
      <span aria-hidden="true">{index + 1 < current ? "✓" : index + 1}</span><strong>{label}{index > 2 && !executionAvailable && <small> · 暂未实现</small>}</strong>
    </li>,
  )}</ol>;
}
