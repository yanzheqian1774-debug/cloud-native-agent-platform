import type { ReactNode } from "react";

import { NavLink } from "react-router-dom";

interface ConsoleShellProps {
  children: ReactNode;
}

export function ConsoleShell({
  children,
}: ConsoleShellProps) {
  return (
    <div className="console-shell">
      <header className="console-header">
        <div className="console-header-inner">
          <NavLink className="console-brand" to="/dashboard">
            <span className="console-brand-mark">
              A
            </span>

            <span>企业智能体平台<small>公开预览 · 资源与数字员工控制台</small></span>
          </NavLink>
        </div>
      </header>

      <aside className="preview-disclosure" role="status">
        <strong>公开预览 / 非生产 / 未认证 / 不代表正式发布</strong>
        <span>数字员工仅为模板定义投影；不存在持久化 Instance 或 Assignment。获批演示仅限进程内，完整运行执行延至 v0.2.3。</span>
      </aside>

      <nav className="global-nav demo-primary-nav" aria-label="主要产品导航">
        <NavLink to="/dashboard">首页</NavLink>
        <NavLink to="/digital-employees">数字员工</NavLink>
        <NavLink to="/catalog">能力与资源</NavLink>
        <NavLink to="/problems">业务任务</NavLink>
        <NavLink to="/tasks">计划与审批</NavLink>
        <NavLink to="/product">执行与结果</NavLink>
        <NavLink to="/evidence">证据</NavLink>
        <NavLink to="/technical">技术详情</NavLink>
      </nav>

      <div className="console-content">
        {children}
      </div>
    </div>
  );
}
