import {DigitalEmployeeRequestError} from '../api/digitalEmployees';
/** Transport waiting does not determine business status or execution outcome. */
export function employeeReadFeedback(error:unknown,signal:AbortSignal){
 if(signal.aborted&&signal.reason?.name==='TimeoutError')return '读取等待时间较长，可重新核对。';
 if(error instanceof DigitalEmployeeRequestError&&(error.status===403||error.status===404))return '当前资源不可读取，请核对访问范围。';
 return '当前读取未完成，可重新核对。';
}
