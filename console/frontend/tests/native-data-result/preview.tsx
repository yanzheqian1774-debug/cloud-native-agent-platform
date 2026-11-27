import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
import {useState} from 'react';
import {PreparedDeliverySummary} from '../../src/problems/PreparedDeliverySummary';
import type {ExecutionView} from '../../src/api/preparedExecution';
import fixture from './controlled-report.json';
import '../../src/styles/product-experience.css';
import '../../src/styles/prototype-frame.css';
const mode=new URLSearchParams(location.search).get('mode');
const value=structuredClone(fixture);
if(mode==='raw-only')delete (value as Partial<typeof value>).nativeReportVerification;
if(mode==='report-mismatch')value.nativeReportVerification.reportDigest='a'.repeat(64);
if(mode==='adapter-mismatch'){value.adapter.configurationDigest='0'.repeat(64);value.nativeReportVerification.adapterDigest='0'.repeat(64);value.nativeReport.adapterDigest='0'.repeat(64)}
if(mode==='source-mismatch')value.sourceSnapshot.digest='0'.repeat(64);
const view={digest:'b'.repeat(64),preparation:{source_snapshot:fixture.sourceSnapshot,plan_version:1,participants:[{task_id:'report',executor_id:'native-synthetic-delivery-readonly',executor_revision:'1',executor_digest:"fe92bb7e92bfce39838c361d22e8ea850c3d76fad3eb8f38e34eee770c13098e",skill:{operation:'RENDER_REPORT'}}],semantics:{tasks:[{task_id:'report',title:'交付资料分析报告'}]}},progress:{state:'SUCCEEDED',tasks:[{task_id:'report',state:'SUCCEEDED'}]},artifacts:[{artifact_id:'artifact-report',task_id:'report',digest:'c'.repeat(64),bytes:12000,created_at:'2026-11-21T00:00:00Z',contentAccess:mode==='unreadable'?'RESTRICTED':'AUTHORIZED',content:JSON.stringify(value)}],outcome:null} as unknown as ExecutionView;
if(mode==='executor-mismatch')view.preparation.participants[0].executor_digest='0'.repeat(64);
export function Preview(){const [selected,setSelected]=useState('');return <main><h1>受控资料分析结果 · 非实际模型验收</h1><PreparedDeliverySummary view={view} viewKey="controlled-native-data" selectedArtifact={selected} onArtifact={setSelected} onCloseArtifact={()=>setSelected('')} query="" onReview={()=>{}}/></main>}
createRoot(document.getElementById('root')!).render(<BrowserRouter><Preview/></BrowserRouter>);
