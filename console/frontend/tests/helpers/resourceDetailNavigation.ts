import type {Page} from '@playwright/test';
/** Business navigation to retained maintenance controls, without another detail page. */
export async function openResourceSection(page:Page,section:string){
 if(await page.getByRole('button',{name:'返回内容',exact:true}).isVisible())await page.getByRole('button',{name:'返回内容',exact:true}).click();
 if(section==='版本'){await page.getByRole('button',{name:'历史记录',exact:true}).click();return}
 if(section==='使用追溯'){await page.getByRole('tab',{name:'引用与影响',exact:true}).click();return}
 await page.getByRole('tab',{name:'内容与定义',exact:true}).click();
 await page.getByRole('button',{name:'发布检查',exact:true}).click();
 await page.getByRole('combobox',{name:'查看配置内容'}).selectOption(section);
}
