import {fixedCycleStatus,cycleScheduledLabel} from './fixedCyclePresentation';

export type ReadableCycleOption={eventId:string;scheduledAt:string|null;recordedAt:string|null;state:string|undefined};
/** Only authoritative readable receipts are passed here; dates never imply execution. */
export function FixedCycleRunSelection({items,selected,timezone,onSelect,newRun,onReadNew}:{items:ReadableCycleOption[];selected:string;timezone:string;onSelect:(event:string)=>void;newRun:boolean;onReadNew:()=>void}){
 return <section className="fixed-cycle-selection" aria-label="固定工作本次运行">
  <label>本次运行 <select aria-label="选择本次运行" value={selected} onChange={e=>onSelect(e.target.value)} disabled={!items.length}>
   {!selected&&<option value="">{items.length?'请选择已读到的运行':'尚无可读运行'}</option>}
   {items.map(row=><option key={row.eventId} value={row.eventId}>{cycleScheduledLabel(row.scheduledAt,timezone)} · {fixedCycleStatus(row.state)}</option>)}
  </select></label>
  {newRun&&<p role="status">有新一次运行 <button type="button" onClick={onReadNew}>查看新运行</button></p>}
 </section>;
}
