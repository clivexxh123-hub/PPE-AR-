type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function GET(_request: Request, { params }: RouteContext) {
  const { jobId } = await params;

  return Response.json({
    jobId,
    status: "queued",
    progress: 8,
    traceId: `trc_${jobId}`,
    message: "Mock 任务已创建；真实 AI Worker 接入后将由队列更新状态。",
  });
}
