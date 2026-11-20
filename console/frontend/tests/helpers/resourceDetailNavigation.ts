import {expect,type Page} from '@playwright/test';
/** Navigate via the single current-content navigation and await its actual state. */
export async function openResourceSection(page:Page,section:string){
 const back=page.getByRole('button',{name:'返回内容',exact:true});
 if(await back.isVisible()){await back.click();await expect(page.getByRole('tab',{name:'概览',exact:true})).toBeVisible();}
 if(section==='版本'){await page.getByRole('button',{name:'历史记录',exact:true}).click();await expect(back).toBeVisible();return;}
 if(section==='使用追溯'){const tab=page.getByRole('tab',{name:'引用与影响',exact:true});await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');return;}
 const tab=page.getByRole('tab',{name:'内容与定义',exact:true});await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');
 await page.getByRole('button',{name:'发布检查',exact:true}).click();
 const target=page.getByRole('navigation',{name:'当前配置内容'}).getByRole('button',{name:section==='管理'?'资源管理':section,exact:true});
 await target.click();await expect(target).toHaveAttribute('aria-current','page');await expect(page.getByRole('tabpanel',{name:section,exact:true})).toBeVisible();
}
