import {useSearchParams} from 'react-router-dom';
import {CurrentWorkDirectory as ExistingDirectory} from './CurrentWorkDirectoryF3';
import {CurrentWorkDirectoryNative} from './CurrentWorkDirectoryNativeF3';
export function CurrentWorkDirectory(props:{outcomes?:boolean;attention?:boolean}){
 const [params]=useSearchParams();
 const inboxKey=props.attention&&import.meta.env.VITE_CURRENT_WORK_DIRECTORY_ENABLED==='true'?(params.get('filter')==='done'?'handled':'pending'):'existing';
 return import.meta.env.VITE_CURRENT_WORK_DIRECTORY_ENABLED==='true'&&!props.outcomes&&!props.attention?<CurrentWorkDirectoryNative/>:<ExistingDirectory key={inboxKey} {...props}/>;
}
