"use client";

import { useEffect, useRef, useState } from "react";

type JobStatus = "idle" | "queued" | "running" | "succeeded";

type Design = {
  x: number;
  y: number;
  scale: number;
  rotation: number;
  color: string;
};

type Timeline = {
  past: Design[];
  present: Design;
  future: Design[];
};

const initialDesign: Design = {
  x: 50,
  y: 42,
  scale: 1,
  rotation: 0,
  color: "#1c77e8",
};

const palette = ["#1c77e8", "#132238", "#e15b44", "#168765", "#ffffff"];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function statusText(status: JobStatus) {
  const map: Record<JobStatus, string> = {
    idle: "待提交",
    queued: "排队中",
    running: "生成中",
    succeeded: "已完成",
  };

  return map[status];
}

export function P0Console() {
  const [timeline, setTimeline] = useState<Timeline>({
    past: [],
    present: initialDesign,
    future: [],
  });
  const [selectedView, setSelectedView] = useState("正面");
  const [selectedLayer, setSelectedLayer] = useState("印标组合");
  const [savedVersions, setSavedVersions] = useState(3);
  const [jobStatus, setJobStatus] = useState<JobStatus>("idle");
  const [jobId, setJobId] = useState("尚未创建任务");
  const [jobProgress, setJobProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerX: number;
    pointerY: number;
    origin: Design;
  } | null>(null);

  const design = timeline.present;

  const commit = (patch: Partial<Design>) => {
    setTimeline((current) => ({
      past: [...current.past.slice(-19), current.present],
      present: { ...current.present, ...patch },
      future: [],
    }));
  };

  const undo = () => {
    setTimeline((current) => {
      const previous = current.past.at(-1);
      if (!previous) return current;
      return {
        past: current.past.slice(0, -1),
        present: previous,
        future: [current.present, ...current.future],
      };
    });
  };

  const redo = () => {
    setTimeline((current) => {
      const next = current.future[0];
      if (!next) return current;
      return {
        past: [...current.past, current.present],
        present: next,
        future: current.future.slice(1),
      };
    });
  };

  const resetDesign = () => {
    setTimeline((current) => ({
      past: [...current.past.slice(-19), current.present],
      present: initialDesign,
      future: [],
    }));
  };

  const beginDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setSelectedLayer("印标组合");
    dragRef.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      origin: design,
    };
    setIsDragging(true);
  };

  useEffect(() => {
    const move = (event: PointerEvent) => {
      const drag = dragRef.current;
      const rect = stageRef.current?.getBoundingClientRect();
      if (!drag || !rect) return;

      const nextX = clamp(
        drag.origin.x + ((event.clientX - drag.pointerX) / rect.width) * 100,
        13,
        87,
      );
      const nextY = clamp(
        drag.origin.y + ((event.clientY - drag.pointerY) / rect.height) * 100,
        14,
        78,
      );

      setTimeline((current) => ({
        ...current,
        present: { ...current.present, x: nextX, y: nextY },
      }));
    };

    const end = () => {
      const drag = dragRef.current;
      if (!drag) return;
      setTimeline((current) => {
        const changed =
          current.present.x !== drag.origin.x || current.present.y !== drag.origin.y;
        if (!changed) return current;
        return {
          past: [...current.past.slice(-19), drag.origin],
          present: current.present,
          future: [],
        };
      });
      dragRef.current = null;
      setIsDragging(false);
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
  }, []);

  const createGeneration = async () => {
    if (jobStatus === "queued" || jobStatus === "running") return;

    const fallbackId = `gen_mock_${Date.now().toString(36)}`;
    setJobStatus("queued");
    setJobProgress(8);
    setJobId(fallbackId);

    try {
      const response = await fetch("/api/v1/generation-jobs", { method: "POST" });
      if (response.ok) {
        const payload = (await response.json()) as { jobId?: string };
        if (payload.jobId) setJobId(payload.jobId);
      }
    } catch {
      // 离线演示时保留本地 Mock 任务，确保前端可独立联调。
    }

    window.setTimeout(() => {
      setJobStatus("running");
      setJobProgress(46);
    }, 650);
    window.setTimeout(() => setJobProgress(78), 1450);
    window.setTimeout(() => {
      setJobStatus("succeeded");
      setJobProgress(100);
    }, 2300);
  };

  const jobCopy: Record<JobStatus, string> = {
    idle: "提交后，任务中心会返回 job_id；AI Worker 只处理任务，不直接写业务库。",
    queued: "已进入队列。KA 演示、普通生成等优先级可在任务中心配置。",
    running: "AI Worker 正在处理，前端可通过轮询或 WebSocket 接收进度。",
    succeeded: "结果已通过 Asset ID 登记。后续可导出、分享或进入人工反馈闭环。",
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">盾</div>
          <div>
            <span className="brand-name">首盾视觉自动化</span>
            <span className="brand-sub">P0 · 核心链路联调原型</span>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="online-dot" aria-hidden="true" />
          <span>Mock API 已就绪</span>
          <span>·</span>
          <span>v0.1</span>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="业务模块">
          <p className="nav-label">P0 核心范围</p>
          <button className="nav-item" type="button"><span className="nav-icon">▦</span>产品与印刷规范</button>
          <button className="nav-item" type="button"><span className="nav-icon">◈</span>客户素材库</button>
          <button className="nav-item is-active" type="button"><span className="nav-icon">✦</span>画布与方案</button>
          <button className="nav-item" type="button"><span className="nav-icon">↗</span>AI 任务中心</button>
          <div className="nav-divider" />
          <p className="nav-label">后续模块</p>
          <button className="nav-item" type="button"><span className="nav-icon">▱</span>导出与分享</button>
          <button className="nav-item" type="button"><span className="nav-icon">◌</span>运营看板</button>
          <div className="release-note">
            <strong>当前可验证</strong>
            <span>画布 JSON、版本快照、生成任务状态与 trace_id 串联。</span>
          </div>
        </aside>

        <main className="main">
          <section className="page-intro">
            <div>
              <p className="eyebrow">P0 / 先跑通一款安全帽</p>
              <h1>产品 → 印标 → 画布 → 方案 → AI 任务</h1>
              <p className="intro-copy">这是一条可独立联调的最小闭环：产品规则来自配置，画布只保存参数与资源引用，AI 通过任务协议接入。</p>
            </div>
            <span className="version-chip">方案 v{savedVersions}.0</span>
          </section>

          <section className="flow-strip" aria-label="核心流程状态">
            <div className="flow-step is-done"><strong>产品与印刷面</strong><span>安全帽 / 正面 / 标定区</span></div>
            <div className="flow-step is-done"><strong>画布编辑</strong><span>拖拽、缩放、旋转、撤销</span></div>
            <div className="flow-step is-next"><strong>任务中心</strong><span>{jobStatus === "idle" ? "等待提交" : statusText(jobStatus)}</span></div>
            <div className="flow-step"><strong>结果与导出</strong><span>本期先固定结果资产</span></div>
          </section>

          <section className="canvas-panel" aria-label="画布编辑器原型">
            <div className="canvas-toolbar">
              <div className="toolbar-title">画布编辑器 <small>画布 Schema v1 · 1280 × 960</small></div>
              <div className="toolbar-actions">
                <button className="btn" type="button" onClick={undo} disabled={!timeline.past.length}>撤销</button>
                <button className="btn" type="button" onClick={redo} disabled={!timeline.future.length}>重做</button>
                <button className="btn" type="button" onClick={resetDesign}>重置</button>
                <button className="btn btn-primary" type="button" onClick={() => setSavedVersions((value) => value + 1)}>保存版本</button>
              </div>
            </div>

            <div className="canvas-grid">
              <aside className="control-rail" aria-label="画布控制">
                <section className="control-section">
                  <p className="section-title">产品与视角</p>
                  <button className="select-product" type="button">安全帽 · SH-100 〈已选〉</button>
                  <div className="view-list" style={{ marginTop: 9 }}>
                    {["正面", "左侧", "右侧", "背面"].map((view) => (
                      <button key={view} className={`view-button ${selectedView === view ? "is-selected" : ""}`} type="button" onClick={() => setSelectedView(view)}>
                        {view}<span>{view === "正面" ? "印刷区 A" : "待配置"}</span>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="control-section">
                  <p className="section-title">印标变换</p>
                  <label className="range-row">尺寸
                    <input aria-label="印标尺寸" type="range" min="0.55" max="1.55" step="0.05" value={design.scale} onChange={(event) => commit({ scale: Number(event.target.value) })} />
                    <span className="range-value">{Math.round(design.scale * 100)}%</span>
                  </label>
                  <label className="range-row">旋转
                    <input aria-label="印标旋转" type="range" min="-25" max="25" step="1" value={design.rotation} onChange={(event) => commit({ rotation: Number(event.target.value) })} />
                    <span className="range-value">{design.rotation}°</span>
                  </label>
                  <div className="color-row" aria-label="印标颜色">
                    {palette.map((color) => <button key={color} className={`color-swatch ${design.color === color ? "is-selected" : ""}`} style={{ background: color }} aria-label={`切换为 ${color}`} type="button" onClick={() => commit({ color })} />)}
                  </div>
                </section>

                <section className="control-section">
                  <p className="section-title">图层</p>
                  <div className="layer-list">
                    <button className={`layer-button ${selectedLayer === "印标组合" ? "is-selected" : ""}`} type="button" onClick={() => setSelectedLayer("印标组合")}>印标组合 <span>Logo + 文字</span></button>
                    <button className={`layer-button ${selectedLayer === "产品底图" ? "is-selected" : ""}`} type="button" onClick={() => setSelectedLayer("产品底图")}>产品底图 <span>锁定</span></button>
                  </div>
                </section>
              </aside>

              <div className="stage-wrap">
                <div ref={stageRef} className="design-stage" aria-label="安全帽正面印标画布">
                  <span className="stage-label">安全帽 · {selectedView} · 印刷区 A</span>
                  <div className="stage-shadow" />
                  <div className="helmet-art" aria-hidden="true"><div className="helmet-dome" /><div className="helmet-band" /><div className="helmet-brim" /></div>
                  <div className="print-area" aria-hidden="true"><span>可印刷区域</span></div>
                  <div className={`artwork ${selectedLayer === "印标组合" ? "is-selected" : ""}`} onPointerDown={beginDrag} style={{ left: `${design.x}%`, top: `${design.y}%`, color: design.color, transform: `translate(-50%, -50%) rotate(${design.rotation}deg) scale(${design.scale})` }}>
                    <span className="wordmark">首盾</span><span className="wordmark-sub">SAFETY PROTECTION</span>
                  </div>
                  <span className="drag-hint">{isDragging ? "正在调整位置" : "拖动印标微调位置"}</span>
                </div>
              </div>
            </div>
          </section>
        </main>

        <aside className="right-rail" aria-label="任务与契约">
          <section className="panel">
            <div className="panel-heading">
              <div><h2>AI 任务中心 · Mock</h2><p>先固定状态机，再替换真实 AI Worker。</p></div>
              <span className={`status-pill ${jobStatus === "running" ? "is-running" : ""} ${jobStatus === "succeeded" ? "is-succeeded" : ""}`}>{statusText(jobStatus)}</span>
            </div>
            <span className="job-id">{jobId}</span>
            <div className="progress-track" aria-label={`任务进度 ${jobProgress}%`}><div className="progress-value" style={{ width: `${jobProgress}%` }} /></div>
            <div className="job-meta"><span>状态机：queued → running → succeeded</span><span>{jobProgress}%</span></div>
            <p className="job-copy">{jobCopy[jobStatus]}</p>
            <button className="btn btn-primary" type="button" onClick={createGeneration} disabled={jobStatus === "queued" || jobStatus === "running"}>{jobStatus === "succeeded" ? "再次创建任务" : "创建 AI 生成任务"}</button>
          </section>

          <section className="panel">
            <div className="panel-heading"><div><h2>已冻结的联调契约</h2><p>数据库、前端与 AI 可以同时开发。</p></div></div>
            <ol className="contract-list">
              <li><span className="contract-number">1</span><div><strong>产品配置</strong><span>product_view、print_area、尺寸规则与标定网格。</span></div></li>
              <li><span className="contract-number">2</span><div><strong>画布快照</strong><span>只存资源 ID 与参数，携带 schema_version。</span></div></li>
              <li><span className="contract-number">3</span><div><strong>任务回调</strong><span>统一 job_id、状态、进度、模型版本与结果 asset_id。</span></div></li>
            </ol>
          </section>

          <section className="trace-card" aria-label="请求追踪">
            <span>本次演示 trace_id</span>
            <code>trc_p0_helmet_design_001</code>
          </section>
        </aside>
      </div>
    </div>
  );
}
