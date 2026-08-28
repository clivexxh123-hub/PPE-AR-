const express = require("express");

const pool = require("../db");
const { requirePermission } = require("../services/iam/access");
const { DashboardStatisticsRepository } = require("../services/dashboard-statistics-repository");
const { DashboardStatisticsService } = require("../services/dashboard-statistics");

const router = express.Router();
const service = new DashboardStatisticsService({
    repository: new DashboardStatisticsRepository(pool)
});

router.get(
    "/statistics",
    requirePermission("records.read_all"),
    async (request, response) => {
        response.json({ success: true, data: await service.get(request.query) });
    }
);

module.exports = router;
