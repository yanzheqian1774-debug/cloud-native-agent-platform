import {expect,test} from '@playwright/test';
import {mcpInvocationOutcome} from '../../src/resources/mcpInvocationOutcome';
import type {SkillMcpResource} from '../../src/api/skillMcpResources';

const receipt:SkillMcpResource['invocations'][number]={invocationId:'call:fixture',revisionId:'revision:exact',revisionDigest:'a'.repeat(64),snapshotId:'snapshot:exact',snapshotDigest:'b'.repeat(64),status:'FAILED',dispatchState:'CALL_ATTEMPTED',reasonCode:'MCP_TIMEOUT',evidence:{redacted:true}};
for(const [dispatch,status,reason,label] of [
 ['CALL_ATTEMPTED','FAILED','MCP_TIMEOUT','调用结果未确认'],
 ['NOT_DISPATCHED','FAILED','MCP_CONNECTION_FAILED','未发出工具调用'],
 ['NOT_DISPATCHED','CANCELLED','CANCELLED_BEFORE_DISPATCH','调用前已取消'],
 ['RESPONSE_RECEIVED','FAILED','MCP_TOOL_REPORTED_ERROR','工具返回错误'],
 ['RESPONSE_RECEIVED','SUCCEEDED','MCP_TOOL_COMPLETED','工具已返回'],
])test(`management result uses dispatch-aware meaning: ${label}`,()=>{
 const outcome=mcpInvocationOutcome({...receipt,dispatchState:dispatch,status,reasonCode:reason});
 expect(outcome.label).toBe(label);
 if(dispatch==='CALL_ATTEMPTED')expect(outcome.note).toContain('可能已产生影响。不会自动重试。');

});
test('legacy technical history cannot invent actual source or business success',()=>{
 const outcome=mcpInvocationOutcome({invocationId:'legacy:call',status:'SUCCEEDED',selectionId:'selection:old',evidence:{redacted:true}});
 expect(outcome.label).toBe('历史调用结果待核实');
 expect(outcome.note).toContain('无法根据选用记录推断实际调用来源或结果');

});
