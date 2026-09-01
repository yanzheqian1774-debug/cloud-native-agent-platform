import { readFile } from "node:fs/promises";
import { createConnection } from "node:net";

type Metadata = { ownershipToken:string; controlSocket:string; backendUrl:string };

export function backendUrl():string {
  const value=process.env.CONSOLE_BACKEND_URL;
  if(!value) throw new Error("CONSOLE_BACKEND_URL is required");
  return value;
}

async function controlOwnedBackend(action:"restart"|"stop"|"start"):Promise<{backendPid:number;backendStartTimeNs:number}> {
  const path=process.env.S5_HARNESS_METADATA;
  const token=process.env.S5_HARNESS_OWNERSHIP_TOKEN;
  if(!path||!token) throw new Error("owned backend harness metadata and token are required");
  const metadata=JSON.parse(await readFile(path,"utf8")) as Metadata;
  if(metadata.ownershipToken!==token||metadata.backendUrl!==backendUrl()) throw new Error("owned backend identity mismatch");
  return new Promise((resolve,reject)=>{
    const socket=createConnection(metadata.controlSocket);
    let response="";
    const providerKeys=["S5_PLANNING_PROVIDER","S5_PLANNING_BASE_URL","S5_PLANNING_API_KEY","S5_PLANNING_MODEL","S5_EMBEDDING_PROVIDER","S5_EMBEDDING_BASE_URL","S5_EMBEDDING_API_KEY","S5_EMBEDDING_MODEL"];
    const environment=Object.fromEntries(providerKeys.flatMap(key=>process.env[key] ? [[key,process.env[key]]] : []));
    socket.on("connect",()=>socket.end(JSON.stringify({action,ownershipToken:token,environment})));
    socket.on("data",chunk=>response+=chunk);
    socket.on("error",reject);
    socket.on("close",()=>{try{const result=JSON.parse(response);if(result.ok) resolve(result);else reject(new Error(result.error));}catch(error){reject(error);}});
  });
}

export const restartOwnedBackend=()=>controlOwnedBackend("restart");
export const stopOwnedBackend=()=>controlOwnedBackend("stop");
export const startOwnedBackend=()=>controlOwnedBackend("start");
