import type {WorkflowContent,WorkflowTask} from "../api/workflowDefinitions";

export type WorkflowGraphIssue={
  id:string;
  code:"DUPLICATE_TASK_ID"|"EMPTY_TASK_ID"|"EMPTY_TASK_NAME"|"SELF_DEPENDENCY"|"DUPLICATE_DEPENDENCY"|"UNKNOWN_DEPENDENCY"|"WORKFLOW_CYCLE";
  message:string;
  taskId?:string;
  field:"taskId"|"name"|"dependsOn";
};

export type WorkflowNodePosition={x:number;y:number};
export type WorkflowLayout={positions:Map<string,WorkflowNodePosition>;width:number;height:number};

export function inspectWorkflowGraph(tasks:WorkflowTask[]):WorkflowGraphIssue[]{
  const issues:WorkflowGraphIssue[]=[];
  const counts=new Map<string,number>();
  for(const task of tasks)counts.set(task.taskId,(counts.get(task.taskId)??0)+1);
  for(const task of tasks){
    const identity=task.taskId||"未命名步骤";
    if(!task.taskId)issues.push({id:`empty-id:${issues.length}`,code:"EMPTY_TASK_ID",message:"步骤 ID 不能为空。",field:"taskId"});
    if(!task.name.trim())issues.push({id:`empty-name:${identity}`,code:"EMPTY_TASK_NAME",message:`${identity} 缺少步骤名称。`,taskId:task.taskId||undefined,field:"name"});
    if(task.taskId&&(counts.get(task.taskId)??0)>1)issues.push({id:`duplicate-id:${task.taskId}`,code:"DUPLICATE_TASK_ID",message:`步骤 ID ${task.taskId} 重复。`,taskId:task.taskId,field:"taskId"});
    const dependencies=new Set<string>();
    for(const dependency of task.dependsOn){
      if(dependency===task.taskId)issues.push({id:`self:${task.taskId}`,code:"SELF_DEPENDENCY",message:`${identity} 不能依赖自身。`,taskId:task.taskId||undefined,field:"dependsOn"});
      if(dependencies.has(dependency))issues.push({id:`duplicate-dependency:${task.taskId}:${dependency}`,code:"DUPLICATE_DEPENDENCY",message:`${identity} 重复依赖 ${dependency}。`,taskId:task.taskId||undefined,field:"dependsOn"});
      dependencies.add(dependency);
      if(!counts.has(dependency))issues.push({id:`unknown:${task.taskId}:${dependency}`,code:"UNKNOWN_DEPENDENCY",message:`${identity} 引用了不存在的依赖 ${dependency}。`,taskId:task.taskId||undefined,field:"dependsOn"});
    }
  }
  const adjacency=new Map(tasks.map(task=>[task.taskId,task.dependsOn.filter(id=>counts.has(id)&&id!==task.taskId)]));
  const visiting=new Set<string>(),visited=new Set<string>(),cyclic=new Set<string>();
  function visit(id:string,path:string[]){
    if(visiting.has(id)){for(const member of path.slice(path.indexOf(id)))cyclic.add(member);return}
    if(visited.has(id))return;
    visiting.add(id);
    for(const dependency of adjacency.get(id)??[])visit(dependency,[...path,dependency]);
    visiting.delete(id);visited.add(id);
  }
  for(const task of tasks)visit(task.taskId,[task.taskId]);
  for(const taskId of cyclic)issues.push({id:`cycle:${taskId}`,code:"WORKFLOW_CYCLE",message:`${taskId} 位于依赖环路中。后端校验仍是权威。`,taskId,field:"dependsOn"});
  return issues;
}

export function layoutWorkflow(tasks:WorkflowTask[]):WorkflowLayout{
  const ids=new Set(tasks.map(task=>task.taskId));
  const level=new Map<string,number>();
  function resolve(task:WorkflowTask,path:Set<string>):number{
    const existing=level.get(task.taskId);if(existing!==undefined)return existing;
    if(path.has(task.taskId))return 0;
    const nextPath=new Set(path).add(task.taskId);
    const parents=task.dependsOn.filter(id=>ids.has(id)&&id!==task.taskId).map(id=>tasks.find(candidate=>candidate.taskId===id)).filter((value):value is WorkflowTask=>Boolean(value));
    const value=parents.length?Math.max(...parents.map(parent=>resolve(parent,nextPath)))+1:0;
    level.set(task.taskId,value);return value;
  }
  for(const task of tasks)resolve(task,new Set());
  const layers=new Map<number,WorkflowTask[]>();
  for(const task of tasks){const taskLevel=level.get(task.taskId)??0;layers.set(taskLevel,[...(layers.get(taskLevel)??[]),task])}
  const positions=new Map<string,WorkflowNodePosition>();
  for(const [taskLevel,layer] of layers)layer.forEach((task,row)=>positions.set(task.taskId,{x:48+taskLevel*270,y:48+row*150}));
  const maxLevel=Math.max(0,...level.values()),maxRows=Math.max(1,...Array.from(layers.values(),items=>items.length));
  return {positions,width:Math.max(660,96+(maxLevel+1)*270),height:Math.max(390,96+maxRows*150)};
}

export function replaceTask(content:WorkflowContent,taskId:string,next:WorkflowTask):WorkflowContent{
  return {...content,tasks:content.tasks.map(task=>task.taskId===taskId?next:task)};
}

export function renameTask(content:WorkflowContent,taskId:string,nextId:string):WorkflowContent{
  return {...content,tasks:content.tasks.map(task=>task.taskId===taskId?{...task,taskId:nextId}:{...task,dependsOn:task.dependsOn.map(dependency=>dependency===taskId?nextId:dependency)})};
}

export function removeTask(content:WorkflowContent,taskId:string):WorkflowContent{
  return {...content,tasks:content.tasks.filter(task=>task.taskId!==taskId).map(task=>task.dependsOn.includes(taskId)?{...task,dependsOn:task.dependsOn.filter(dependency=>dependency!==taskId)}:task)};
}

export function nextTaskId(tasks:WorkflowTask[]):string{
  const used=new Set(tasks.map(task=>task.taskId));let value=tasks.length+1;
  while(used.has(`step-${value}`))value+=1;
  return `step-${value}`;
}
