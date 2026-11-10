import {CurrentWorkDirectory as ExistingDirectory} from './CurrentWorkDirectoryF3';
import {CurrentWorkDirectoryNative} from './CurrentWorkDirectoryNativeF3';
export function CurrentWorkDirectory(props:{outcomes?:boolean;attention?:boolean}){
 return import.meta.env.VITE_CURRENT_WORK_DIRECTORY_ENABLED==='true'&&!props.outcomes&&!props.attention?<CurrentWorkDirectoryNative/>:<ExistingDirectory {...props}/>;
}
