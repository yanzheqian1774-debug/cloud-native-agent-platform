export type ProductRelationship={relation:string;sourceKind?:string;sourceIdentity?:string;sourceRevisionId?:string|null;targetKind:string;targetIdentity:string;targetRevisionId?:string;targetDigest?:string};
export type ProductResource={kind:string;identity:string;name:string;revisionId:string|null;digest:string|null;lifecycleStatus:string;capabilityStatus:string;owner:string|null;compatibility:string;limitations:string[];capabilities:string[];relationships:ProductRelationship[];consumers:unknown[];reviewStatus:string;deepLink:string};
export type ProductDashboard={resourceCount:number;countsByKind:Record<string,number>;countsByLifecycle:Record<string,number>;attentionCount:number;capabilityGapCount:number;authority:string;limitations:string[]};
export type AttentionItem=Pick<ProductResource,"kind"|"identity"|"revisionId"|"digest"|"deepLink">&{status:string;reason:string};
export type DigitalEmployeeTemplate={templateId:string;name:string;purpose:string;agentDefinition:{identity:string;revisionId:string|null;digest:string|null};composition:ProductRelationship[];readiness:string;limitations:string[];executionAuthority:"NONE";deepLink:string};
export class ProductAssemblyError extends Error{reasonCode:string;status:number;constructor(reasonCode:string,status:number){super(reasonCode);this.reasonCode=reasonCode;this.status=status}}
async function request<T>(path:string):Promise<T>{let response:Response;try{response=await fetch(path,{headers:{Accept:"application/json"}})}catch{throw new ProductAssemblyError("PRODUCT_ASSEMBLY_NETWORK_UNAVAILABLE",503)}const body=await response.json().catch(()=>null);if(!response.ok)throw new ProductAssemblyError(body?.detail?.reasonCode??"PRODUCT_ASSEMBLY_UNAVAILABLE",response.status);return body as T}
const root="/api/internal/v0.2.2/product";
export const getProductDashboard=()=>request<ProductDashboard>(`${root}/dashboard`);
export const listProductResources=(query="",kind="",status="")=>request<ProductResource[]>(`${root}/catalog?${new URLSearchParams({query,kind,status})}`);
export const listProductRelationships=()=>request<ProductRelationship[]>(`${root}/relationships`);
export const listAttention=()=>request<AttentionItem[]>(`${root}/attention`);
export const listDigitalEmployeeTemplates=()=>request<DigitalEmployeeTemplate[]>(`${root}/digital-employee-templates`);
