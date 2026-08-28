require("../server");

// Keep the local demo process alive when it is launched from a detached
// Windows terminal. Production deployments continue to use PM2 + server.js.
const keepAlive = setInterval(() => {}, 60_000);

function shutdown() {
    clearInterval(keepAlive);
    process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
