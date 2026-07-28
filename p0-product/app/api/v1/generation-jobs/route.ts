export async function POST() {
  const jobId = `gen_mock_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;

  return Response.json(
    {
      jobId,
      status: "queued",
      traceId: `trc_${jobId}`,
      pollUrl: `/api/v1/generation-jobs/${jobId}`,
    },
    { status: 202 },
  );
}
